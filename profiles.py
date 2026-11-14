"""Persistent, named IP camera profiles. URLs are never returned by the API."""
import json
import os
from pathlib import Path
from threading import RLock
from urllib.parse import urlsplit, urlunsplit, quote
from uuid import uuid4
from camera import Camera


class Profiles:
    LIMIT = 8

    def __init__(self, default, path=None, factory=None):
        self.default = default
        self.path = Path(path) if path else None
        self.factory = factory or (lambda source: Camera(source, fps=default.fps, quality=default.quality, backend='ffmpeg'))
        self.lock = RLock()
        self.items, self.workers = {}, {}
        self.closed = False
        if self.path and self.path.exists():
            rows = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(rows, dict) or len(rows) > self.LIMIT:
                raise ValueError('Invalid camera profile store')
            for key, row in rows.items():
                if len(key) != 32 or any(c not in '0123456789abcdef' for c in key):
                    raise ValueError('Invalid camera ID')
                self.items[key] = self.validate(row)

    @staticmethod
    def validate(data, previous=None):
        if not isinstance(data, dict):
            raise ValueError('Expected a JSON object')
        name = data.get('name', '')
        source = data.get('source', '') or (previous or {}).get('source', '')
        if not isinstance(name, str) or not name.strip() or len(name) > 80:
            raise ValueError('Enter a name of 1–80 characters')
        if not isinstance(source, str) or len(source) > 2048 or any(c.isspace() or ord(c) < 32 for c in source):
            raise ValueError('Enter a valid stream URL without spaces')
        try:
            u = urlsplit(source)
            if u.scheme not in ('rtsp', 'rtsps', 'http', 'https') or not u.hostname or u.fragment:
                raise ValueError()
            _ = u.port
            if data.get('secure') is True and u.scheme not in ('https','rtsps'):
                raise ValueError('Secure transport requires HTTPS or RTSPS')
            username, password = data.get('username',''), data.get('password','')
            if not isinstance(username,str) or not isinstance(password,str) or len(username)>128 or len(password)>512 or (password and not username):
                raise ValueError('Invalid camera credentials')
            if username:
                if not data.get('source'): raise ValueError('Enter stream URL when replacing credentials')
                netloc = quote(username,safe='') + ':' + quote(password,safe='') + '@' + u.netloc.rsplit('@',1)[-1]
                source = urlunsplit((u.scheme,netloc,u.path,u.query,''))
                if len(source)>2048: raise ValueError('Stream URL too long')
        except ValueError:
            raise ValueError('Use a valid RTSP, RTSPS, HTTP or HTTPS URL and credentials; secure transport requires RTSPS or HTTPS') from None
        return {'name': name.strip(), 'source': source}

    def _save(self, rows):
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            tmp = self.path.with_name('.' + self.path.name + '.' + uuid4().hex)
            try:
                fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                    json.dump(rows, handle, ensure_ascii=False, indent=2)
                os.replace(tmp, self.path)
            finally:
                tmp.unlink(missing_ok=True)
        self.items = rows

    def list(self):
        with self.lock:
            return [{'id': 'default', 'name': 'Demo' if self.default.demo else 'Default camera', 'editable': False}] + [
                {'id': key, 'name': row['name'], 'editable': True} for key, row in self.items.items()]

    def get(self, key):
        with self.lock:
            if self.closed:
                raise KeyError(key)
            if key == 'default':
                return self.default
            if key not in self.items:
                raise KeyError(key)
            if key not in self.workers:
                cam = self.factory(self.items[key]['source'])
                cam.start()
                self.workers[key] = cam
            return self.workers[key]

    def put(self, data, key=None):
        with self.lock:
            if self.closed:
                raise KeyError(key)
            if key is None:
                if len(self.items) >= self.LIMIT:
                    raise ValueError('Camera limit reached (8 saved profiles)')
                key = uuid4().hex
            elif key not in self.items:
                raise KeyError(key)
            row = self.validate(data, self.items.get(key))
            changed = self.items.get(key, {}).get('source') != row['source']
            self._save({**self.items, key: row})
            if changed and key in self.workers:
                self.workers.pop(key).stop()
            return {'id': key, 'name': row['name'], 'editable': True}

    def delete(self, key):
        with self.lock:
            if key not in self.items:
                raise KeyError(key)
            rows = dict(self.items)
            del rows[key]
            self._save(rows)
            if key in self.workers:
                self.workers.pop(key).stop()

    def close(self):
        with self.lock:
            self.closed = True
            workers = [self.default, *self.workers.values()]
            self.workers.clear()
        # Signal every capture before waiting on individual workers.
        for cam in workers:
            cam.stop_event.set()
            with cam.changed:
                cam.changed.notify_all()
        for cam in workers:
            cam.stop()
