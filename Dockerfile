FROM python:3.15.2-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home --home-dir /app --shell /usr/sbin/nologin app
COPY requirements.txt .
RUN python -m pip install --only-binary=:all: -r requirements.txt
COPY camera.py profiles.py security.py pyWCam.py docker-healthcheck.py ./
COPY templates ./templates
COPY static ./static
RUN mkdir -p /data && chown 10001:10001 /data && chmod 700 /data
ENV PYWCAM_CONFIG=/data/cameras.json
VOLUME ["/data"]
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD ["python", "/app/docker-healthcheck.py"]
ENTRYPOINT ["python", "pyWCam.py", "--lan"]
CMD ["--demo"]
