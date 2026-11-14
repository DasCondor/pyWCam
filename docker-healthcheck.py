"""Docker process HTTP liveness; camera readiness is /healthz."""
import os
import ssl
from urllib.error import HTTPError
from urllib.request import urlopen

try:
    with urlopen(('https' if os.getenv('PYWCAM_TLS_CERT') else 'http') + '://127.0.0.1:8080/', timeout=3, context=ssl._create_unverified_context() if os.getenv('PYWCAM_TLS_CERT') else None) as response:
        raise SystemExit(0 if response.status == 200 else 1)
except HTTPError as exc:
    # An authentication challenge proves the listener responds without leaking secrets.
    raise SystemExit(0 if exc.code == 401 else 1)
except OSError:
    raise SystemExit(1)
