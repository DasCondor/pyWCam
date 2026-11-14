import base64
import http.client
import json
import ssl
import threading
import time
import unittest
from security import Auth, totp, decode_secret, new_secret
from camera import Camera
from pyWCam import Server

SECRET = base64.b32encode(b'12345678901234567890').decode()
PASSWORD = 'testing-only-password'

class SecurityTests(unittest.TestCase):
    def test_rfc_vector(self):
        self.assertEqual(totp(decode_secret(SECRET), 59//30, 8), '94287082')
        self.assertEqual(len(decode_secret(new_secret())),20)
        with self.assertRaises(ValueError): decode_secret('ABCD')

    def test_rate_limit_expiry_and_replay(self):
        auth = Auth(b'viewer:'+PASSWORD.encode(), SECRET, ttl=.01)
        code = totp(auth.key,int(time.time())//30)
        status, token = auth.login('viewer',PASSWORD,code)
        self.assertEqual(status,200)
        self.assertTrue(auth.valid(token))
        self.assertEqual(auth.login('viewer',PASSWORD,code)[0],401)
        time.sleep(.03)
        self.assertFalse(auth.valid(token))
        for _ in range(8): self.assertEqual(auth.login('viewer','bad',code)[0],401)
        self.assertEqual(auth.login('viewer',PASSWORD,code)[0],429)

    def test_mfa_requires_tls_on_lan(self):
        with self.assertRaises(ValueError): Server(('0.0.0.0',0),Camera(demo=True),PASSWORD,mfa_secret=SECRET)

    def test_mfa_http_routes(self):
        cam=Camera(width=320,height=180,demo=True); cam.start()
        server=Server(('127.0.0.1',0),cam,PASSWORD,mfa_secret=SECRET)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        def call(path, method='GET', data=None, headers=None):
            c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=4)
            try:
                c.request(method,path,body=json.dumps(data) if data is not None else None,headers=headers or {})
                r=c.getresponse();return r.status,dict(r.getheaders()),r.read()
            finally:c.close()
        try:
            self.assertIn(b'Verification code',call('/')[2])
            for path in ('/api/status','/snapshot.jpg','/video_feed','/api/cameras'):
                self.assertEqual(call(path)[0],401)
            basic='Basic '+base64.b64encode(f'viewer:{PASSWORD}'.encode()).decode()
            self.assertEqual(call('/api/status',headers={'Authorization':basic})[0],401)
            data={'username':'viewer','password':PASSWORD,'code':totp(decode_secret(SECRET),int(time.time())//30)}
            self.assertEqual(call('/api/login','POST',data,{'Content-Type':'application/json'})[0],403)
            headers={'Content-Type':'application/json','X-PyWCam':'1'}
            status,h,_=call('/api/login','POST',data,headers)
            self.assertEqual(status,200);self.assertIn('HttpOnly',h['Set-Cookie']);self.assertIn('SameSite=Strict',h['Set-Cookie'])
            cookie=h['Set-Cookie'].split(';')[0]
            self.assertEqual(call('/api/status',headers={'Cookie':cookie})[0],200)
            self.assertEqual(call('/api/login','POST',data,headers)[0],401)
            self.assertEqual(call('/api/logout','POST',headers={'Cookie':cookie,'X-PyWCam':'1'})[0],200)
            self.assertEqual(call('/api/status',headers={'Cookie':cookie})[0],401)
        finally:cam.stop();server.shutdown();server.server_close();worker.join()

class CameraCredentialTests(unittest.TestCase):
    def test_credentials_and_secure_scheme(self):
        from profiles import Profiles
        row=Profiles.validate({'name':'Parking','source':'rtsps://192.0.2.10:322/stream','username':'a@b','password':'p:/?#','secure':True})
        self.assertEqual(row['source'],'rtsps://a%40b:p%3A%2F%3F%23@192.0.2.10:322/stream')
        with self.assertRaises(ValueError): Profiles.validate({'name':'Parking','source':'rtsp://192.0.2.10/stream','secure':True})
