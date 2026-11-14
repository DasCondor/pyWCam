# pyWCam 2.0

![pyWCam 2.0 — USB and IP camera viewer](docs/header.svg)

[![Python 3.15](https://img.shields.io/badge/Python-3.15-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/release/python-3152/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](#quick-start-with-docker)
[![Version](https://img.shields.io/badge/version-2.0.0-555)](CHANGELOG.md)

View USB webcams and IP cameras from a browser on your own computer or trusted local network. No cloud account, no external UI libraries, no server-side recording.

**[Open the public sandbox ↗](https://dascondor.github.io/pyWCam/)** (available after the Pages workflow is deployed) · [Docker setup](#quick-start-with-docker) · [Add cameras](#add-ip-cameras) · [Native installation](#native-installation-no-docker)

## Public sandbox

Try the actual layout with browser-generated test pattern, garage, front door, parking lot and offline camera simulations. Switch sources, add/edit/remove mock profiles, pause, mirror, expand and download a sample JPG. No backend, camera permissions, editable real URL fields or network requests are used by the demo. Changes reset on reload.

To run locally, open `docs/demo/index.html` in a browser. It is a single self-contained HTML file. To update the demo after layout changes, run `python demo/build.py`.

To publish: in GitHub **Settings → Pages**, choose **GitHub Actions** as the source, then run the **Sandbox demo** workflow. It publishes only the generated static sandbox, never the Python server or saved camera profiles.

## What's new in 2.0

- A simpler interface with a camera pane, snapshot pane, toolbar and status strip. On a phone the panes stack and the controls are touch-sized. System, Light and Dark theme preferences are available and remembered by the browser.
- Shared camera capture and JPEG encoding across viewers instead of reading the webcam separately for every connection.
- USB and RTSP/HTTP camera sources, automatic reconnect attempts, resolution and frame-rate options, and a synthetic demo source.
- Add, rename, replace or remove up to eight saved IP camera profiles from the interface. Each viewer can select their own camera.
- Python 3.15 target, Docker 3.15.2 base image and GitHub Pages sandbox.
- Pause/resume, mirror, expanded view, JPG snapshots and live camera statistics.
- Docker and Docker Compose configurations for demo, Linux USB webcams, and network cameras.
- Local-only access by default; username/password authentication for LAN access, optional TOTP MFA and HTTPS.
- Windows setup script, automated tests and GitHub Actions for Python and Docker.

## Quick start with Docker

Install Docker with the Compose v2 plugin (Docker Desktop includes it). From the repository directory:

```bash
git clone https://github.com/DasCondor/pyWCam.git
cd pyWCam
docker compose up -d --build
docker compose logs pywcam
```

Open <http://127.0.0.1:8080>. The default source is a moving synthetic test pattern, not a real camera. You can add authorized IP cameras from the interface. Sign in with `viewer` and the generated session password printed in the logs.

```bash
docker compose ps
docker compose logs -f pywcam
docker compose down
```

### Docker configuration

Copy `.env.example` to `.env` (`cp .env.example .env` on Linux; `Copy-Item .env.example .env` in PowerShell), then edit it. Don't commit this file.

| Variable | Default / purpose |
| --- | --- |
| `PYWCAM_BIND` | `127.0.0.1`; set to `0.0.0.0` for trusted LAN access |
| `PYWCAM_PORT` | `8080` (host port; internal port stays 8080) |
| `PYWCAM_USERNAME` | `viewer` |
| `PYWCAM_PASSWORD` | Empty generates a password at each start; use 12+ characters for a fixed password |
| `PYWCAM_VIDEO_DEVICE` | `/dev/video0` on the Linux host |
| `PYWCAM_VIDEO_GID` | Numeric host camera group ID; required for USB Compose override |
| `PYWCAM_WIDTH`, `PYWCAM_HEIGHT` | `1280`, `720` for USB Compose override |
| `PYWCAM_FPS` | `15` for USB and network Compose overrides |
| `PYWCAM_SOURCE` | Authorized RTSP/HTTP(S) URL for network Compose override |

Changes to `.env` take effect when Compose recreates the container. The service runs as a non-root user with a read-only filesystem, dropped capabilities and no privileged mode. The Docker health check monitors HTTP listener liveness; the authenticated `/healthz` endpoint reports camera readiness.

### Linux USB webcam (including supported Raspberry Pi USB cameras)

Find the correct device and its group ID on the Linux host:

```bash
ls -l /dev/video*
stat -c '%g' /dev/video0
```

Set `PYWCAM_VIDEO_DEVICE` and `PYWCAM_VIDEO_GID` in `.env`. Close any other program using the camera, then run:

```bash
docker compose -f compose.yaml -f compose.usb.yaml up -d --build
docker compose -f compose.yaml -f compose.usb.yaml logs -f pywcam
```

The selected device maps to `/dev/video0` in the container. Device access is subject to host permissions, Docker configuration and compatible OpenCV/V4L2 drivers. Raspberry Pi CSI/libcamera cameras are not explicitly supported. Docker Desktop does not automatically expose Windows/macOS USB webcams as Linux video devices; use the native Python method for those webcams.

### RTSP / IP camera

Set `PYWCAM_SOURCE` in `.env` to your camera's authorized video stream URL, for example:

```dotenv
PYWCAM_SOURCE='rtsp://user:password@192.168.1.10:554/stream'
```

Then:

```bash
docker compose -f compose.yaml -f compose.rtsp.yaml up -d --build
```

The container must be able to reach the camera over the network. OpenCV/FFmpeg support varies by codec, transport and camera. Credentials in source URLs may appear in native diagnostic logs; protect your logs and `.env` file. Audio is not streamed.

### Docker without Compose

```bash
docker build -t pywcam:2.0.0 .
docker run --rm --init -p 127.0.0.1:8080:8080 pywcam:2.0.0
```

The image defaults to demo mode. Supply application arguments after the image name to select a real source; keep internal port 8080 so the health check remains valid. No prebuilt registry image is published by this project update.

## Add IP cameras

1. Start pyWCam natively or with Docker (even the default Docker demo source works as a starting point).
2. Select **Add IP camera** and enter a display name and the authorized camera's actual video stream URL.
3. Select **Save camera**. The viewer opens that camera and shows its connection status.
4. Switch between saved cameras using the Camera list. Use **Edit** to rename or replace the URL (leave it blank to retain the current URL), or **Remove** to delete the profile.

Example URLs (documentation placeholders, not public cameras):

| Protocol | Example |
|---|---|
| RTSP | `rtsp://192.0.2.10:554/stream` |
| Authenticated RTSP | `rtsp://user:password@192.0.2.10:554/stream` |
| HTTP MJPEG | `http://192.0.2.10:8080/video` |
| HTTPS | `https://camera.example.invalid/video` |

Use a stream endpoint, not the camera's administration webpage. ONVIF discovery and PTZ controls are not implemented. Compatibility depends on OpenCV/FFmpeg and your camera. The host/container must be able to reach the camera. Eight saved profiles plus the default source are supported; each source gets its own worker when first selected, and active viewers of that source share frames. Started workers stay active until the source is removed/replaced or the application stops.

Profiles are stored in `~/.pywcam/cameras.json` (override via `--config` or `PYWCAM_CONFIG`); Docker Compose persists them in the `camera-config` volume. URLs and credentials are not returned by the camera list API, but **are stored in plaintext** in the private configuration file. Restrict file access and backup access. `docker compose down` retains profiles; `docker compose down -v` deletes them. All authenticated users can manage cameras, so give access only to trusted operators. The real server can connect to operator-supplied network addresses; do not expose it to untrusted users or the public internet. The static public sandbox cannot make such connections.

## Native installation (no Docker)

Target runtime: **Python 3.15 (64-bit recommended)**. The Windows installer and CI require 3.15; Docker uses 3.15.2. Dependency installation and the test suite were run on Python 3.15.2 for Windows; see [VALIDATION.md](VALIDATION.md).

**Windows — PowerShell 5.1 or later:**

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Demo
```

Remove `-Demo` for a real webcam. Add `-Lan -Port 3000` to share on a trusted private network. `-InstallOnly` installs dependencies without starting the server.

**Linux / macOS / Raspberry Pi (64-bit OS recommended):**

```bash
python3.15 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r requirements.txt
.venv/bin/python pyWCam.py --demo
```

If a Python 3.15 OpenCV/NumPy wheel is unavailable on your platform, the binary-only installer will stop rather than compile dependencies. On Windows you can also install using your Python environment directly:

```powershell
python -m pip install --only-binary=:all: -r requirements.txt
python pyWCam.py --source 0
```

Open <http://127.0.0.1:8080>. Stop with Ctrl+C.

## Usage

```bash
python pyWCam.py --demo
python pyWCam.py --source 1 --width 1280 --height 720 --fps 15
python pyWCam.py --source 0 --backend dshow
python pyWCam.py --lan --port 3000
python pyWCam.py -host -po 3000 -iid 2
python pyWCam.py -iid 1
```

| Option | Description |
| --- | --- |
| `--source` | USB index or RTSP/HTTP(S) URL; can use `PYWCAM_SOURCE` |
| `--backend` | `auto`, `dshow`, `msmf`, `v4l2`, `ffmpeg` |
| `--width`, `--height` | Requested USB capture dimensions; network streams use their original size |
| `--fps` | Target maximum frame rate (1–60) |
| `--quality` | JPEG quality (10–95, default 80) |
| `--max-viewers` | Concurrent video streams (1–64, default 8) |
| `--lan`, `--hosted`, `-host` | Listen on all IPv4 interfaces with authentication |
| `--port`, `-po` | HTTP port (default 8080) |
| `--HTMLIndexID`, `-iid` | 1 for compact viewer; 2 for camera and snapshot panes (default) |
| `--username` | Authentication username (default `viewer`) |
| `--demo` | Synthetic default source; saved IP camera profiles remain available |
| `--config` | Camera profile JSON path (`PYWCAM_CONFIG`) |
| `--version` | Display version |

Pause stops your own viewer stream, not the camera. Mirror affects the preview only. Capture photo takes a JPEG from the latest frame, then Save JPG downloads it to your device. Compact mode downloads directly. The server does not save photos or video. Stop the application to release the webcam.

## Local network access

For native installation use `--lan`. For Docker set `PYWCAM_BIND=0.0.0.0` in `.env`. Open `http://HOST-LAN-IP:8080` from a device on the same trusted network. On Windows use `ipconfig` to find your host address. Permit the selected port on trusted private networks only, if necessary.

LAN mode requires authentication (HTTP Basic by default, or optional MFA sessions). The default username is `viewer`; a random password is printed unless `PYWCAM_PASSWORD` is configured (minimum 12 characters). HTTP does **not** encrypt credentials or video. Do not port-forward this application or expose the built-in server to the internet. For authorized remote use, use a trusted VPN or correctly configured HTTPS reverse proxy. Only stream cameras you own or have permission to use, with appropriate notice and consent.

## HTTP endpoints

| Route | Purpose |
| --- | --- |
| `/` | Browser viewer |
| `/video_feed` | Shared MJPEG video stream |
| `/snapshot.jpg` | Latest JPEG (503 if unavailable) |
| `/api/status` | JSON camera state, frame size, measured FPS, viewers and reconnects |
| `/healthz` | 200 when camera is live; otherwise 503 |
| `/api/cameras` | GET list of camera profiles; POST add a profile |
| `/api/cameras/{id}` | PUT edit or DELETE remove a saved profile |

Stream, status, snapshot and health endpoints accept `?camera=<id>`; default is `default`. Camera mutations require JSON (where applicable) and the `X-PyWCam: 1` header. All routes require authentication when enabled. Viewer limit applies across all cameras. Actual frame rate depends on the hardware and network. Reconnect is best-effort; a hung native driver may require a restart. This application is designed for a small trusted LAN, not as a production public streaming server.

## Project layout

```text
pyWCam.py              HTTP server and CLI
camera.py              Capture, JPEG encoding and reconnects
profiles.py            Saved IP camera profiles and independent workers
demo/                  Browser-only sandbox source and generator
docs/demo/index.html    Self-contained static sandbox
docs/header.svg         Repository banner
static/                CSS and JavaScript
templates/             Camera viewer
Dockerfile             Container image
compose.yaml           Default demo service
compose.usb.yaml       Linux webcam override
compose.rtsp.yaml      Network camera override
docker-healthcheck.py  HTTP liveness check
.env.example           Docker configuration example
install.ps1            Windows setup
.github/workflows/    Python and Docker CI
tests/                 Unit/integration and browser checks
```

## Tests

```bash
python -m unittest discover -s tests -v
python -m pip install playwright
python -m playwright install chromium
python tests/browser_smoke.py
python tests/browser_sandbox.py
```

The backend tests use synthetic frames and fake hardware. The optional browser smoke test exercises the live local server. `python tests/browser_preview.py` exercises the interface using fixture HTTP responses; it is not a live MJPEG test. The sandbox browser test checks desktop/mobile controls, photo downloads, profile editing and absence of external requests. GitHub Actions is configured to run the Python tests on Windows/Linux, validate all Compose configurations, build the Docker image, and check demo endpoints. See [VALIDATION.md](VALIDATION.md) for actual results and outstanding hardware/container tests.

## Upgrading from 0.1.x

The original `-host`, `-po`, `-iid` and `/video_feed` remain available. The two-pane layout is now the default. Flask and its separate templates were replaced by a standard-library HTTP server and a single responsive interface. The old `setup.py` is obsolete. LAN access now requires a password.

The original project is [DasCondor/pyWCam](https://github.com/DasCondor/pyWCam). Thanks to Alfren for the original HTML templates. The old setup declared AGPL; the exact license version and full license text should be confirmed by the repository owner before release. This update does not relicense the project.

## Optional security and MFA

The server supports three access modes: local-only without a login, password authentication (the existing default for LAN hosting), and password plus a six-digit TOTP authenticator code. MFA is opt-in and configured by the server operator, not by an unauthenticated visitor. All users share the configured server identity; this is not a multi-user authorization system.

### Enable MFA for a native installation

Generate a random Base32 enrollment key once:

```bash
python pyWCam.py --generate-mfa-secret
```

In an authenticator app (Microsoft Authenticator, Google Authenticator, 1Password, etc.), add an account manually using that key: time-based, six digits, 30-second interval, SHA-1. Keep an offline backup of the key. Set a unique password of at least 12 characters and the generated key in the server's environment (do not commit either secret). For PowerShell:

```powershell
$env:PYWCAM_USERNAME = 'viewer'
$env:PYWCAM_PASSWORD = Read-Host 'Enter a unique server password'
$env:PYWCAM_MFA_SECRET = Read-Host 'Enter the authenticator enrollment key'
python pyWCam.py --demo
```

Visit `http://127.0.0.1:8080`; sign in with the password and current authenticator code. For real camera operation omit `--demo`. The server refuses MFA on non-loopback interfaces without TLS. To host with MFA on your LAN, set `PYWCAM_TLS_CERT` and `PYWCAM_TLS_KEY` to matching PEM files before adding `--lan`; use a trusted certificate that matches the server hostname, and open its HTTPS address. TLS 1.2 or newer is required. Do not bypass browser certificate warnings.

### Enable Docker MFA and HTTPS

1. Generate the enrollment key with the command above or `docker compose run --rm --no-deps pywcam --generate-mfa-secret`.
2. Put your fixed `PYWCAM_PASSWORD`, generated `PYWCAM_MFA_SECRET`, and optional `PYWCAM_TLS_DIR` in `.env`. Protect the file from other users.
3. Supply a trusted certificate as `tls/cert.pem` and its private key as `tls/key.pem` (or use the directory specified by `PYWCAM_TLS_DIR`). Ensure the container user UID 10001 can read the key without granting unnecessary permissions.
4. Start the service:

```bash
docker compose -f compose.yaml -f compose.tls.yaml up -d --build
```

For a physical camera or RTSP source, include the applicable `compose.usb.yaml` or `compose.rtsp.yaml` override before `compose.tls.yaml`. Open the trusted HTTPS hostname on your configured port. The internal health check verifies listener liveness only; it does not validate the certificate identity or expose credentials.

### What the security features do (and do not do)

- TOTP follows RFC 6238, using a 30-second period and accepting the current or immediately preceding period. Consumed codes cannot be reused within the running process. Restarting the server clears replay tracking and sessions.
- MFA sessions expire after eight hours, use randomized server-side tokens, and can be revoked by signing out. Session cookies are HttpOnly, SameSite=Strict and Secure for HTTPS. Active streams check the session on each frame cycle.
- The MFA login endpoint allows ten attempts per rolling minute across the server, including successful attempts. This limits brute force but can cause temporary denial of login on a busy or hostile LAN. Password-only Basic mode does not use this MFA rate limiter.
- Camera usernames/passwords are independent of the server login. Saved profiles support embedded URL credentials or the separate credential fields (percent-encoded on the server). The optional secure-transport checkbox checks the URL scheme; it does not guarantee camera certificate validation by OpenCV/FFmpeg. Verify camera TLS behavior before using it on an untrusted network.
- Camera URLs are never returned by the API. The JSON profile file is permission-restricted on POSIX but **not encrypted at rest**; protect its directory and Docker volume, and restrict Windows ACLs. Camera URLs may be seen by the capture backend. Protect secrets in environment variables and backups. Do not distribute `.env`, TLS private keys or saved camera profiles.
- This remains a trusted-LAN utility, not an internet-facing surveillance platform. Do not port-forward. The server does not include per-user roles, recovery codes, phishing-resistant passkeys or an external identity provider. To recover from a lost authenticator, stop the server and replace the MFA secret with a newly generated one through local administrative access.

### Sandbox security and theme

The public demo includes an Add IP Camera dialog with locked sample URLs, simulated camera credentials, protocol choices and a Security dialog that simulates turning MFA on and signing in. No real credentials, URL connections, camera permissions or API calls are used. System, Light and Dark theme options are saved locally in the browser when browser storage is available. The garage and front-door scenes use generated still images; the parking lot currently uses a drawn illustrative scene with a simulated timestamp.
