import base64
import http.client
import json
import threading
import time
import unittest

import cv2
import numpy as np
from camera import Camera
from pyWCam import Server, parse_args


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.camera = Camera(width=320, height=180, fps=10, demo=True)
        cls.camera.start()
        cls.server = Server(('127.0.0.1', 0), cls.camera, 'example-test-password', max_viewers=1)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        end = time.monotonic() + 4
        while cls.camera.latest() is None and time.monotonic() < end:
            time.sleep(.02)

    @classmethod
    def tearDownClass(cls):
        cls.camera.stop(); cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def request(self, path, auth=True, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=4)
        h = dict(headers or {})
        if auth:
            h['Authorization'] = 'Basic ' + base64.b64encode(b'viewer:example-test-password').decode()
        conn.request('GET', path, headers=h)
        return conn, conn.getresponse()

    def test_auth_every_route(self):
        for path in ['/', '/api/status', '/video_feed', '/snapshot.jpg', '/static/app.js', '/healthz']:
            conn, r = self.request(path, False)
            self.assertEqual(r.status, 401); r.read(); conn.close()

    def test_status_and_assets(self):
        for p in ['/', '/static/app.css', '/static/app.js', '/healthz', '/api/status']:
            conn, r = self.request(p); self.assertEqual(r.status, 200); body = r.read(); conn.close()
        status = json.loads(body)
        self.assertEqual(status['mode'], 'demo'); self.assertEqual(status['width'], 320)
        self.assertEqual(status['state'], 'live')

    def test_jpeg(self):
        conn, r = self.request('/snapshot.jpg'); jpeg = r.read(); conn.close()
        self.assertEqual(r.status, 200)
        frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(frame.shape[:2], (180, 320))

    def test_multipart_and_limit(self):
        conn, r = self.request('/video_feed')
        try:
            self.assertEqual(r.status, 200)
            self.assertEqual(r.readline(), b'--frame\r\n')
            self.assertEqual(r.readline(), b'Content-Type: image/jpeg\r\n')
            size = int(r.readline().split(b':')[1]); self.assertEqual(r.readline(), b'\r\n')
            self.assertTrue(r.read(size).startswith(b'\xff\xd8'))
            other, blocked = self.request('/video_feed'); self.assertEqual(blocked.status, 503); blocked.read(); other.close()
        finally:
            r.close(); conn.close()

    def test_bad_host_and_paths(self):
        for p, h, code in [('/', {'Host':'evil.example'}, 403), ('/camera.py', {}, 404), ('/../camera.py', {}, 404)]:
            conn, r = self.request(p, headers=h); self.assertEqual(r.status, code); r.read(); conn.close()

    def test_lan_requires_password(self):
        with self.assertRaises(ValueError): Server(('0.0.0.0',0), self.camera)

    def test_legacy_args(self):
        a = parse_args(['-host','-po','3000','-iid','1'])
        self.assertTrue(a.hosted); self.assertEqual((a.port,a.HTMLIndexID), (3000,1))


class RecoveryTests(unittest.TestCase):
    def test_reconnect_and_single_producer(self):
        calls = []
        class Fake:
            def __init__(self, works): self.works = works
            def isOpened(self): return self.works
            def read(self): return True, np.zeros((120,160,3), dtype=np.uint8)
            def release(self): pass
        def factory():
            calls.append(1); return Fake(len(calls)>1)
        cam = Camera(fps=10, factory=factory); cam.start()
        try:
            end = time.monotonic()+5
            while cam.latest() is None and time.monotonic()<end: time.sleep(.02)
            self.assertIsNotNone(cam.latest()); self.assertEqual(len(calls), 2)
            self.assertEqual(cam.status()['reconnects'], 1)
            with cam.changed:
                seq, image = cam.wait_frame(-1); seq2, image2 = cam.wait_frame(-1)
                self.assertEqual(seq, seq2); self.assertIs(image, image2)
        finally: cam.stop()
        self.assertEqual(cam.status()['state'], 'stopped')

if __name__ == '__main__': unittest.main()
