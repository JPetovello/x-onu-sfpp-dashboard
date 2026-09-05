FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/data

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt \
    && python -m pip uninstall -y pip

COPY app.py .
COPY advanced.py .
COPY web_templates ./web_templates
COPY static ./static

RUN mkdir -p /data

EXPOSE 8080

CMD ["gunicorn", "--workers", "1", "--threads", "4", "--bind", "0.0.0.0:8080", "--access-logfile", "-", "app:app"]
