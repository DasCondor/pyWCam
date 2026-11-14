import base64
import http.client
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from camera import Camera
from profiles import Profiles
from pyWCam import Server


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'cameras.json'
        self.default = Camera(demo=True, width=320, height=180)
        self.default.start()
        self.profiles = Profiles(self.default, self.path, factory=lambda url: Camera(demo=True, width=160, height=120))
        self.server = Server(('127.0.0.1', 0), self.default, 'example-test-password', profiles=self.profiles)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.profiles.close(); self.server.server_close(); self.thread.join(); self.tmp.cleanup()

    def request(self, method, path, data=None, auth=True, mutation=True, extra=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=8)
        headers = {'Content-Type': 'application/json'}
        if auth:
            headers['Authorization'] = 'Basic ' + base64.b64encode(b'viewer:example-test-password').decode()
        if mutation:
            headers['X-PyWCam'] = '1'
        headers.update(extra or {})
        try:
            conn.request(method, path, body=json.dumps(data) if data is not None else None, headers=headers)
            res = conn.getresponse()
            return res.status, res.read()
        finally:
            conn.close()

    def add(self, name='Garage', source='rtsp://user:secret@192.0.2.10:554/live'):
        status, body = self.request('POST', '/api/cameras', {'name':name,'source':source})
        self.assertEqual(status, 201, body)
        return json.loads(body)['id']

    def test_add_edit_delete_and_reload(self):
        key = self.add()
        self.assertIn('secret', self.path.read_text())
        _, body = self.request('GET', '/api/cameras')
        self.assertNotIn(b'secret', body); self.assertNotIn(b'192.0.2.10', body)
        self.assertEqual(json.loads(body)[1]['id'], key)
        restored = Profiles(self.default, self.path)
        self.assertEqual(restored.list(), self.profiles.list())
        status, body = self.request('PUT', '/api/cameras/'+key, {'name':'Back door','source':''})
        self.assertEqual(status, 200); self.assertIn('secret', self.path.read_text())
        self.assertEqual(json.loads(body)['name'], 'Back door')
        self.assertEqual(self.request('DELETE', '/api/cameras/'+key)[0],200)
        self.assertEqual(json.loads(self.path.read_text()), {})
        self.assertEqual(self.request('GET','/api/status?camera='+key)[0],404)

    def test_independent_streams_and_worker_replacement(self):
        key = self.add(); cam = self.profiles.get(key)
        self.assertIs(cam, self.profiles.get(key)); self.assertIsNot(cam,self.default)
        end = time.monotonic()+4
        while cam.latest() is None and time.monotonic()<end: time.sleep(.02)
        status, body = self.request('GET','/snapshot.jpg?camera='+key)
        self.assertEqual(status,200); self.assertTrue(body.startswith(b'\xff\xd8'))
        _, body = self.request('GET','/api/status?camera='+key)
        self.assertEqual(json.loads(body)['width'],160)
        _, body = self.request('GET','/api/status')
        self.assertEqual(json.loads(body)['width'],320)
        self.assertEqual(self.request('PUT','/api/cameras/'+key,{'name':'New','source':'http://192.0.2.1/stream'})[0],200)
        self.assertTrue(cam.stop_event.is_set()); self.assertIsNot(cam,self.profiles.get(key))
        self.request('DELETE','/api/cameras/'+key)

    def test_mutations_require_auth_and_same_origin(self):
        data={'name':'Test','source':'rtsp://192.0.2.1/live'}
        for kwargs, status in [({'auth':False},401),({'mutation':False},403),({'extra':{'Origin':'http://evil.example'}},403)]:
            self.assertEqual(self.request('POST','/api/cameras',data,**kwargs)[0],status)
        self.assertEqual(self.request('GET','/api/cameras',auth=False)[0],401)
        self.assertEqual(self.request('DELETE','/api/cameras/default')[0],404)
        self.assertFalse(self.path.exists())

    def test_invalid_urls_and_limit(self):
        for url in ['file:///etc/passwd','ftp://example.com','rtsp://','http://host:bad','http://host/a b','']:
            self.assertEqual(self.request('POST','/api/cameras',{'name':'Test','source':url})[0],400)
        for n in range(self.profiles.LIMIT): self.add(str(n))
        self.assertEqual(self.request('POST','/api/cameras',{'name':'Extra','source':'rtsp://192.0.2.1/live'})[0],400)

    def test_http_network_camera(self):
        # Real FFmpeg/OpenCV capture over loopback MJPEG, from the synthetic server.
        upstream = Server(('127.0.0.1',0), self.default)
        thread = threading.Thread(target=upstream.serve_forever,daemon=True); thread.start()
        cam = Camera(f'http://127.0.0.1:{upstream.server_port}/video_feed',fps=10,backend='ffmpeg')
        cam.start()
        try:
            end=time.monotonic()+8
            while cam.latest() is None and time.monotonic()<end: time.sleep(.05)
            self.assertIsNotNone(cam.latest())
            self.assertEqual(cam.status()['width'],320)
        finally:
            cam.stop(); upstream.shutdown(); upstream.server_close(); thread.join()

if __name__ == '__main__': unittest.main()
