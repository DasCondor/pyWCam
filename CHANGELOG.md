# Changelog

## 2.0.0 (proposed)
- Replaced the original request-driven camera loop with a shared capture/encoding worker.
- Added configurable source, backend, size, quality and capture rate.
- Added retry handling, health and stats endpoints, viewer limits and demo mode.
- Rebuilt the dashboard for touch and desktop use, including snapshots and expanded preview.
- LAN access now requires authentication; loopback remains the default.
- Added a Windows installer, Dockerfile and GitHub Actions CI.
- Removed Flask and obsolete standard-library dependencies; only OpenCV and NumPy are needed.
- Reworked the web UI into a conventional two-pane webcam utility, with system light/dark mode and touch-sized controls.
- Added Compose configurations for demo, Linux USB and RTSP sources; non-root container, HTTP liveness check and graceful SIGTERM handling.
- Added Docker build/smoke-test CI and documented Docker, environment options, native installation and migration in the README.
- Added saved IP camera profiles, UI management, independent per-camera workers, profile API, and a persistent Docker volume.
- Target Python 3.15, using Python 3.15.2 in Docker and 3.15 in CI and the Windows installer.
- Added a self-contained public camera sandbox, preset-only mock sources, GitHub Pages deployment and refreshed README/banner.

### Security and preferences

- Optional TOTP MFA, expiring sessions, logout, login throttling and replay protection.
- Native TLS 1.2+ and Docker TLS override; LAN MFA fails closed without TLS.
- Camera credential fields and secure URL scheme selection.
- System/Light/Dark preferences and simulated security dialog in the sandbox.
