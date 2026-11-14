"""pyWCam 2.0 - local and trusted LAN webcam server."""
import argparse
import base64
import hmac
import ipaddress
import json
import logging
import os
from pathlib import Path
import secrets
import signal
import ssl
from http.cookies import SimpleCookie, CookieError
from security import Auth, new_secret
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import BoundedSemaphore
from urllib.parse import urlsplit, parse_qs

from camera import Camera
from profiles import Profiles

VERSION = '2.0.0'
ROOT = Path(__file__).resolve().parent
LOG = logging.getLogger('pyWCam')
ASSETS = {'/': ('templates/index.html', 'text/html; charset=utf-8'),
          '/static/app.css': ('static/app.css', 'text/css; charset=utf-8'),
          '/static/app.js': ('static/app.js', 'text/javascript; charset=utf-8'),
          '/static/theme.js': ('static/theme.js', 'text/javascript; charset=utf-8')}


class Server(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, camera, password=None, username='viewer', max_viewers=8, compact=False, profiles=None, mfa_secret=None, tls_context=None):
        self.camera, self.compact = camera, compact
        self.profiles = profiles or Profiles(camera)
        self.credentials = (username + ':' + password).encode('utf-8') if password is not None else None
        self.tls = tls_context is not None
        self.auth = Auth(self.credentials, mfa_secret) if mfa_secret and self.credentials else None
        if mfa_secret and self.auth is None:
            raise ValueError('MFA requires a password')
        if self.auth and not ipaddress.ip_address(address[0]).is_loopback and not self.tls:
            raise ValueError('MFA on non-loopback interfaces requires TLS')
        self.stream_slots = BoundedSemaphore(max_viewers)
        self.request_slots = BoundedSemaphore(max_viewers + 16)
        super().__init__(address, Handler)
        if tls_context:
            self.socket = tls_context.wrap_socket(self.socket, server_side=True, do_handshake_on_connect=False)
        self.loopback_only = ipaddress.ip_address(self.server_address[0]).is_loopback
        if not self.loopback_only and self.credentials is None:
            self.server_close()
            raise ValueError('Non-loopback binding requires authentication')

    def process_request(self, request, client_address):
        if not self.request_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.request_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.request_slots.release()


class Handler(BaseHTTPRequestHandler):
    server_version = 'pyWCam/' + VERSION
    sys_version = ''
    def setup(self):
        self.request.settimeout(10)
        if self.server.tls:
            self.request.do_handshake()
        super().setup()

    def log_message(self, fmt, *args):
        # Individual frame/status requests are intentionally not logged.
        pass

    def response_headers(self, code, kind, length=None, extra=None):
        self.send_response(code)
        self.send_header('Content-Type', kind)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        if length is not None:
            self.send_header('Content-Length', str(length))
        if extra:
            for name, value in extra.items():
                self.send_header(name, value)
        self.end_headers()

    def send_bytes(self, code, kind, body, extra=None):
        self.response_headers(code, kind, len(body), extra)
        self.wfile.write(body)

    def text(self, code, msg, extra=None):
        self.send_bytes(code, 'text/plain; charset=utf-8', msg.encode(), extra)

    def token(self):
        try:
            cookie = SimpleCookie(self.headers.get('Cookie', ''))
            return cookie['pywcam_session'].value if 'pywcam_session' in cookie else ''
        except CookieError:
            return ''

    def session_cookie(self, value, age):
        return f'pywcam_session={value}; Path=/; Max-Age={age}; HttpOnly; SameSite=Strict' + ('; Secure' if self.server.tls else '')

    def same_origin(self):
        host = self.headers.get('Host', '')
        origin = self.headers.get('Origin')
        return self.headers.get('X-PyWCam') == '1' and (not origin or origin == ('https://' if self.server.tls else 'http://') + host)

    def auth_post(self, path):
        if not self.server.auth or not self.same_origin():
            self.json(403, {'error': 'Authentication endpoint unavailable'}); return
        if path == '/api/logout':
            self.server.auth.logout(self.token())
            self.send_bytes(200, 'application/json', b'{}', {'Set-Cookie': self.session_cookie('', 0)}); return
        size = self.headers.get('Content-Length', '')
        if self.headers.get_content_type() != 'application/json' or not size.isascii() or not size.isdecimal() or len(size) > 4 or not 0 < int(size) <= 2048:
            self.json(400, {'error': 'Invalid request'}); return
        try:
            data = json.loads(self.rfile.read(int(size)))
            if not isinstance(data, dict): raise ValueError()
            code, token = self.server.auth.login(data.get('username'), data.get('password'), data.get('code'))
        except (ValueError, UnicodeError):
            self.json(400, {'error': 'Invalid request'}); return
        if token:
            self.send_bytes(200, 'application/json', b'{}', {'Set-Cookie': self.session_cookie(token, self.server.auth.ttl)})
        else:
            self.json(code, {'error': 'Too many attempts. Try again in one minute.' if code == 429 else 'Invalid login or verification code.'})

    def valid_host(self):
        # Restrict loopback host headers to mitigate DNS rebinding.
        if self.server.loopback_only:
            try:
                h = urlsplit('//' + self.headers.get('Host', '')).hostname
            except ValueError:
                h = None
            if h not in ('localhost', '127.0.0.1'):
                self.text(403, 'Invalid local host')
                return False
        return True

    def authorized(self):
        if not self.valid_host(): return False
        if self.server.auth:
            if self.server.auth.valid(self.token()): return True
            self.text(401, 'Sign in required'); return False
        if self.server.credentials is None:
            return True
        auth = self.headers.get('Authorization', '').split(' ', 1)
        try:
            supplied = base64.b64decode(auth[1], validate=True) if len(auth) == 2 and auth[0].lower() == 'basic' else b''
        except (ValueError, TypeError):
            supplied = b''
        if not hmac.compare_digest(supplied, self.server.credentials):
            self.text(401, 'Authentication required', {'WWW-Authenticate': 'Basic realm="pyWCam", charset="UTF-8"'})
            return False
        return True

    def json(self, code, body):
        self.send_bytes(code, 'application/json', json.dumps(body).encode())

    def mutate(self, method):
        try:
            if not self.authorized():
                return
            # A custom header makes cross-origin browser requests preflight; no CORS is enabled.
            origin = self.headers.get('Origin')
            host = self.headers.get('Host', '')
            if self.headers.get('X-PyWCam') != '1' or (origin and origin not in ('http://' + host, 'https://' + host)):
                self.json(403, {'error': 'Same-origin camera management required'})
                return
            path = urlsplit(self.path).path
            key = path.removeprefix('/api/cameras/') if path.startswith('/api/cameras/') else None
            if method == 'POST' and path != '/api/cameras' or method != 'POST' and not key:
                self.json(404, {'error': 'Not found'})
                return
            if method == 'DELETE':
                self.server.profiles.delete(key)
                self.json(200, {'deleted': True})
                return
            if self.headers.get_content_type() != 'application/json':
                self.json(415, {'error': 'Expected JSON'})
                return
            length = self.headers.get('Content-Length', '')
            size = int(length) if length.isascii() and length.isdecimal() and len(length) <= 5 else 0
            if not 0 < size <= 8192:
                self.json(400, {'error': 'Invalid request size'})
                return
            try:
                data = json.loads(self.rfile.read(size))
            except (ValueError, UnicodeError):
                self.json(400, {'error': 'Invalid JSON'})
                return
            self.json(201 if method == 'POST' else 200, self.server.profiles.put(data, key))
        except KeyError:
            self.json(404, {'error': 'Camera not found'})
        except ValueError as exc:
            self.json(400, {'error': str(exc)})
        except (BrokenPipeError, ConnectionResetError, TimeoutError, ConnectionAbortedError):
            pass
        except OSError:
            self.json(500, {'error': 'Could not save camera settings'})

    def do_POST(self):
        path = urlsplit(self.path).path
        if path in ('/api/login', '/api/logout'):
            if self.valid_host(): self.auth_post(path)
        else: self.mutate('POST')
    def do_PUT(self): self.mutate('PUT')
    def do_DELETE(self): self.mutate('DELETE')

    def do_GET(self):
        try:
            url = urlsplit(self.path)
            path = url.path
            if self.server.auth and path in ('/', '/static/login.js', '/static/app.css', '/static/theme.js'):
                if not self.valid_host(): return
                if path == '/' and not self.server.auth.valid(self.token()):
                    self.send_bytes(200, 'text/html; charset=utf-8', (ROOT/'templates/login.html').read_bytes()); return
                if path == '/static/login.js':
                    self.send_bytes(200, 'text/javascript; charset=utf-8', (ROOT/'static/login.js').read_bytes()); return
                if path in ASSETS:
                    name, mime = ASSETS[path]
                    self.send_bytes(200, mime, (ROOT/name).read_bytes()); return
            if not self.authorized(): return
            if path in ASSETS:
                name, mime = ASSETS[path]
                self.send_bytes(200, mime, (ROOT / name).read_bytes())
            elif path == '/api/cameras':
                self.json(200, self.server.profiles.list())
            elif path in ('/api/status', '/healthz', '/snapshot.jpg', '/video_feed'):
                key = 'default' if path == '/healthz' else parse_qs(url.query).get('camera', ['default'])[0]
                cam = self.server.profiles.get(key)
                self.camera_response(path, cam)
            else:
                self.text(404, 'Not found')
        except KeyError:
            self.json(404, {'error': 'Camera not found'})
        except (BrokenPipeError, ConnectionResetError, TimeoutError, ConnectionAbortedError):
            pass

    def camera_response(self, path, cam):
        if path in ('/api/status', '/healthz'):
            status = cam.status()
            status.update(version=VERSION, compact=self.server.compact, mfa=bool(self.server.auth), tls=self.server.tls)
            self.send_bytes(200 if path != '/healthz' or status['state'] == 'live' else 503,
                            'application/json', json.dumps(status).encode())
        elif path == '/snapshot.jpg':
            jpeg = cam.latest()
            if jpeg is None:
                self.text(503, 'Camera unavailable')
            else:
                self.send_bytes(200, 'image/jpeg', jpeg)
        elif path == '/video_feed':
            self.stream(cam)

    def stream(self, cam):
        if not self.server.stream_slots.acquire(blocking=False):
            self.text(503, 'Viewer limit reached')
            return
        with cam.changed:
            cam.viewers += 1
        try:
            self.response_headers(200, 'multipart/x-mixed-replace; boundary=frame', extra={'X-Accel-Buffering': 'no'})
            seq, empty = -1, 0
            while not cam.stop_event.is_set():
                if self.server.auth and not self.server.auth.valid(self.token()): break
                seq, jpeg = cam.wait_frame(seq)
                if jpeg is None:
                    empty += 1
                    if empty >= 8:
                        break
                    continue
                empty = 0
                self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ' + str(len(jpeg)).encode() + b'\r\n\r\n' + jpeg + b'\r\n')
        finally:
            with cam.changed:
                cam.viewers -= 1
            self.server.stream_slots.release()


def parse_args(argv=None):
    p = argparse.ArgumentParser(description='Host a webcam on your computer or trusted LAN.')
    p.add_argument('--generate-mfa-secret', action='store_true', help='Generate a Base32 authenticator key and exit')
    p.add_argument('--version', action='version', version=VERSION)
    p.add_argument('-host', '--hosted', '--lan', action='store_true', help='Bind to all IPv4 interfaces; requires credentials')
    p.add_argument('-po', '--port', type=int, default=8080)
    p.add_argument('-iid', '--HTMLIndexID', type=int, choices=(1, 2), default=2, help='1: compact; 2: dashboard (new default)')
    p.add_argument('--source', default=os.getenv('PYWCAM_SOURCE', '0'), help='USB camera index or network stream URL; prefer environment for credentials')
    p.add_argument('--backend', choices=('auto','dshow','msmf','v4l2','ffmpeg'), default='auto')
    p.add_argument('--width', type=int, default=1280)
    p.add_argument('--height', type=int, default=720)
    p.add_argument('--fps', type=int, default=15)
    p.add_argument('--quality', type=int, default=80)
    p.add_argument('--max-viewers', type=int, default=8)
    p.add_argument('--username', default=os.getenv('PYWCAM_USERNAME', 'viewer'))
    p.add_argument('--config', default=os.getenv('PYWCAM_CONFIG', str(Path.home() / '.pywcam' / 'cameras.json')), help='Saved camera profile JSON path')
    p.add_argument('--demo', action='store_true', help='Synthetic camera; does not access hardware')
    a = p.parse_args(argv)
    for name, low, high in [('port',1,65535),('width',160,3840),('height',120,2160),('fps',1,60),('quality',10,95),('max_viewers',1,64)]:
        if not low <= getattr(a,name) <= high:
            p.error(f'{name} must be between {low} and {high}')
    if not a.username or ':' in a.username:
        p.error('username must be nonempty and contain no colon')
    if a.source.isdecimal():
        a.source = int(a.source)
    elif not a.source.lower().startswith(('rtsp://','rtsps://','http://','https://')):
        p.error('source must be a camera index or an RTSP/HTTP(S) URL')
    return a


def main(argv=None):
    a = parse_args(argv)
    if a.generate_mfa_secret:
        print(new_secret()); return
    mfa_secret = os.getenv('PYWCAM_MFA_SECRET') or None
    cert, key = os.getenv('PYWCAM_TLS_CERT'), os.getenv('PYWCAM_TLS_KEY')
    context = None
    if cert or key:
        if not cert or not key: raise SystemExit('Set both PYWCAM_TLS_CERT and PYWCAM_TLS_KEY')
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(cert, key)
    if mfa_secret and a.hosted and not context:
        raise SystemExit('MFA LAN access requires a TLS certificate and key.')
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    password = os.getenv('PYWCAM_PASSWORD') or None
    if mfa_secret and not password: raise SystemExit("MFA requires a fixed PYWCAM_PASSWORD")
    generated = a.hosted and password is None
    if generated:
        password = secrets.token_urlsafe(18)
    if password is not None and len(password) < 12:
        raise SystemExit('PYWCAM_PASSWORD must be at least 12 characters.')
    camera = Camera(a.source, a.width, a.height, a.fps, a.quality, a.backend, a.demo)
    try:
        profiles = Profiles(camera, a.config)
    except (ValueError, OSError, TypeError, AttributeError):
        raise SystemExit('Could not load camera profile store. Check its format and permissions.') from None
    try:
        server = Server(('0.0.0.0' if a.hosted else '127.0.0.1', a.port), camera, password, a.username, a.max_viewers, a.HTMLIndexID == 1, profiles, mfa_secret, context)
    except ValueError as e:
        raise SystemExit(str(e)) from None
    except OSError as e:
        raise SystemExit(f'Could not bind port {a.port}: {e.strerror}') from None
    scheme = 'https' if context else 'http'
    print(f'pyWCam {VERSION} | {scheme}://127.0.0.1:{a.port}', flush=True)
    if a.hosted:
        print(f'LAN: {scheme}://<host-LAN-IP>:{a.port} | username: {a.username}', flush=True)
        if generated:
            print(f'Generated session password: {password}', flush=True)
        print('Trusted LAN only. Do not port-forward.' if context else 'Trusted LAN only: HTTP is not encrypted. Do not port-forward.', flush=True)
    def terminate(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminate)
    camera.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        profiles.close()
        server.server_close()


if __name__ == '__main__':
    main()
