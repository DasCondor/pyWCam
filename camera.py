"""Single-producer JPEG camera with reconnect and synthetic demo source."""
import logging
import threading
import time
from datetime import datetime, timezone

import cv2
import numpy as np

LOG = logging.getLogger(__name__)


class Camera:
    def __init__(self, source=0, width=1280, height=720, fps=15, quality=80,
                 backend='auto', demo=False, factory=None):
        self.source, self.width, self.height = source, width, height
        self.fps, self.quality, self.backend, self.demo = fps, quality, backend, demo
        self.factory = factory or self._open
        self.changed = threading.Condition()
        self.stop_event = threading.Event()
        self.thread = None
        self.frame, self.seq, self.updated = None, 0, 0.0
        self.state, self.size, self.rate = 'starting', None, 0.0
        self.viewers, self.reconnects = 0, 0

    def _open(self):
        api = {'auto': cv2.CAP_ANY, 'dshow': cv2.CAP_DSHOW,
               'msmf': cv2.CAP_MSMF, 'v4l2': cv2.CAP_V4L2,
               'ffmpeg': cv2.CAP_FFMPEG}[self.backend]
        if isinstance(self.source, str) and self.source.lower().startswith(('rtsp://', 'rtsps://', 'http://', 'https://')):
            if self.backend == 'auto':
                api = cv2.CAP_FFMPEG
            cap = cv2.VideoCapture(self.source, api, [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000,
                                                       cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000])
        else:
            cap = cv2.VideoCapture(self.source, api)
        if isinstance(self.source, int) and cap.isOpened():
            for prop, val in ((cv2.CAP_PROP_FRAME_WIDTH, self.width),
                              (cv2.CAP_PROP_FRAME_HEIGHT, self.height),
                              (cv2.CAP_PROP_FPS, self.fps)):
                cap.set(prop, val)
        return cap

    def start(self):
        if self.thread is None:
            self.thread = threading.Thread(target=self._run, name='camera', daemon=True)
            self.thread.start()

    def stop(self):
        self.stop_event.set()
        with self.changed:
            self.changed.notify_all()
        if self.thread:
            self.thread.join(timeout=6)

    def _offline(self):
        with self.changed:
            self.frame, self.state, self.rate = None, 'reconnecting', 0.0
            self.reconnects += 1
            self.changed.notify_all()

    def _synthetic(self):
        w, h = self.width, self.height
        frame = np.full((h, w, 3), (25, 34, 43), dtype=np.uint8)
        for x in range(0, w, max(32, w // 12)):
            cv2.line(frame, (x, 0), (x, h), (45, 56, 67), 1)
        for y in range(0, h, max(32, h // 8)):
            cv2.line(frame, (0, y), (w, y), (45, 56, 67), 1)
        x = int((time.monotonic() * 90) % max(1, w - 2 * min(w, h) // 9)) + min(w, h) // 9
        cv2.circle(frame, (x, int(h * .53)), max(8, min(w, h) // 9), (151, 219, 102), -1)
        scale = max(.35, min(w / 1000, h / 500))
        cv2.putText(frame, 'pyWCam / DEMO', (int(w*.05), int(h*.17)), cv2.FONT_HERSHEY_SIMPLEX, scale, (235, 241, 245), 2, cv2.LINE_AA)
        cv2.putText(frame, datetime.now(timezone.utc).strftime('%H:%M:%S UTC'), (int(w*.05), int(h*.89)), cv2.FONT_HERSHEY_SIMPLEX, scale*.7, (205, 215, 224), 1, cv2.LINE_AA)
        return frame

    def _run(self):
        cap = None
        last = None
        while not self.stop_event.is_set():
            tick = time.monotonic()
            try:
                if self.demo:
                    frame = self._synthetic()
                else:
                    if cap is None:
                        cap = self.factory()
                    if not cap.isOpened():
                        raise RuntimeError('camera unavailable')
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        raise RuntimeError('frame unavailable')
                ok, jpg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
                if not ok:
                    raise RuntimeError('JPEG encoding failed')
                now = time.monotonic()
                with self.changed:
                    if last is not None and now > last:
                        rate = 1 / (now - last)
                        self.rate = rate if self.rate == 0 else self.rate * .9 + rate * .1
                    self.frame = jpg.tobytes()
                    self.seq += 1
                    self.updated = now
                    self.state = 'live'
                    self.size = (int(frame.shape[1]), int(frame.shape[0]))
                    self.changed.notify_all()
                last = now
            except Exception:
                LOG.warning('Camera unavailable; retrying in 2 seconds')
                if cap is not None:
                    cap.release()
                    cap = None
                last = None
                self._offline()
                self.stop_event.wait(2)
                continue
            self.stop_event.wait(max(0, 1/self.fps - (time.monotonic() - tick)))
        if cap is not None:
            cap.release()
        with self.changed:
            self.state, self.frame = 'stopped', None
            self.changed.notify_all()

    def latest(self):
        with self.changed:
            if self.frame is not None and time.monotonic() - self.updated <= 5:
                return self.frame
            return None

    def wait_frame(self, previous, timeout=1):
        with self.changed:
            self.changed.wait_for(lambda: (self.seq != previous and self.frame is not None)
                                  or self.stop_event.is_set(), timeout)
            if self.seq == previous or self.frame is None or time.monotonic() - self.updated > 5:
                return previous, None
            return self.seq, self.frame

    def status(self):
        with self.changed:
            age = time.monotonic() - self.updated if self.updated else None
            state = self.state if self.state != 'live' or (age is not None and age <= 5) else 'stalled'
            return {'state': state, 'mode': 'demo' if self.demo else 'camera',
                    'width': self.size[0] if self.size else None, 'height': self.size[1] if self.size else None,
                    'fps': round(self.rate, 1) if state == 'live' else 0,
                    'frames': self.seq, 'viewers': self.viewers, 'reconnects': self.reconnects,
                    'age_seconds': round(age, 2) if age is not None else None}
