"""Optional local TOTP authentication and bounded in-memory sessions (RFC 6238)."""
import base64
import hashlib
import hmac
import secrets
import time
from collections import deque
from threading import Lock


def decode_secret(value):
    value = value.strip().replace(' ', '').upper().rstrip('=')
    try:
        key = base64.b32decode(value + '=' * (-len(value) % 8))
    except (ValueError, TypeError):
        raise ValueError('MFA secret must be valid Base32') from None
    if len(key) < 20:
        raise ValueError('MFA secret must contain at least 160 bits')
    return key


def new_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode('ascii')


def totp(key, counter, digits=6):
    raw = hmac.digest(key, counter.to_bytes(8, 'big'), 'sha1')
    offset = raw[-1] & 15
    return str((int.from_bytes(raw[offset:offset+4], 'big') & 0x7fffffff) % (10**digits)).zfill(digits)


class Auth:
    def __init__(self, credentials, secret, ttl=8*3600):
        self.credentials, self.key, self.ttl = credentials, decode_secret(secret), ttl
        self.sessions, self.attempts = {}, deque()
        self.last_counter = -1
        self.lock = Lock()

    def login(self, username, password, code):
        now = time.monotonic()
        with self.lock:
            while self.attempts and self.attempts[0] <= now - 60:
                self.attempts.popleft()
            if len(self.attempts) >= 10:
                return 429, None
            self.attempts.append(now)
            if not all(isinstance(v, str) for v in (username, password, code)):
                return 401, None
            if not hmac.compare_digest((username + ':' + password).encode(), self.credentials) or len(code) != 6 or not code.isascii() or not code.isdecimal():
                return 401, None
            counter = int(time.time()) // 30
            match = next((c for c in (counter, counter-1) if c >= 0 and c > self.last_counter and hmac.compare_digest(totp(self.key, c), code)), None)
            if match is None:
                return 401, None
            self.last_counter = match
            self.sessions = {k:v for k,v in self.sessions.items() if v > now}
            if len(self.sessions) >= 64:
                self.sessions.pop(min(self.sessions, key=self.sessions.get))
            token = secrets.token_urlsafe(32)
            self.sessions[hashlib.sha256(token.encode()).digest()] = now + self.ttl
            return 200, token

    def valid(self, token):
        with self.lock:
            return self.sessions.get(hashlib.sha256(token.encode()).digest(), 0) > time.monotonic()

    def logout(self, token):
        with self.lock:
            self.sessions.pop(hashlib.sha256(token.encode()).digest(), None)
