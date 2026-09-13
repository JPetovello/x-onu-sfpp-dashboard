FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/data
ENV HOME=/tmp

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt \
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

CMD ["gunicorn", "--workers", "1", "--threads", "4", "--bind", "0.0.0.0:8080", "--access-logfile", "-", "app:app"]
