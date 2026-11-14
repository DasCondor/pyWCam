# pyWCam 2.0.0 security update validation

## Executed successfully

- 18 Python unit and integration tests passed on Windows 11 with Python 3.15.2 (NumPy 2.5.4, opencv-python-headless 4.14.0.94, installed from binary wheels only) and earlier on Linux with Python 3.13.5: original stream/profile tests, credential URL encoding, secure-scheme validation, RFC 6238 vector, MFA enforcement (including Basic bypass attempt), replay protection, rate limiting, expiry, logout and same-origin checks.
- Separate real TLS smoke test passed: trusted test certificate, HTTPS MFA login and Secure cookie. Temporary keys were removed.
- JavaScript syntax checks, YAML parsing and static sandbox build succeeded. Rebuilding with `python demo/build.py` reproduces the committed `docs/demo/index.html`. The sandbox uses locked sample endpoints, embedded scenes and a CSP that disallows network connections. No actual camera data is used.

## Not verified locally

- Docker build, Compose validation, live container operation and the Chromium sandbox test were not run locally; they run in GitHub Actions (see the Tests workflow for current results). YAML parsing is not Compose schema validation.
- No physical USB/RTSP cameras, third-party authenticator apps or camera TLS certificate validation were tested. This is not a penetration test or security audit.
- Garage and front-door feeds are generated stills; the parking-lot scene is drawn, not photorealistic.