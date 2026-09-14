FROM python:3.13-slim@sha256:9d2e5553305c7c7b0097999bb17187c69b921ccd6bc9d40e4bb5ebe652c00285

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/data
ENV HOME=/tmp

WORKDIR /app

COPY requirements.lock .

RUN pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements.lock \
    && python -m pip uninstall -y pip \
    && mkdir -p /data /tmp/.gunicorn \
    && chown -R 99:100 /app /data /tmp/.gunicorn

COPY app.py .
COPY advanced.py .
COPY alerts.py .
COPY tx_health.py .
COPY notifications.py .
COPY retention.py .
COPY web_templates ./web_templates
COPY static ./static

RUN chown -R 99:100 /app

USER 99:100

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=3).read()"]

CMD ["gunicorn", "--workers", "1", "--threads", "4", "--bind", "0.0.0.0:8080", "--access-logfile", "-", "app:app"]
