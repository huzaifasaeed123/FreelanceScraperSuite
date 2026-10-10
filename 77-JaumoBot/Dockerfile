FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STORAGE_DIR=/app/storage

# ffmpeg converts uploaded voice memos (mp3/m4a/wav/aac) to OGG/Opus, the only format Telegram plays as a voice message
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot
COPY api ./api
COPY modules ./modules
COPY frontend ./frontend

# Single persistent volume: database, photos, legacy accounts import.
RUN mkdir -p /app/storage/photos
VOLUME ["/app/storage"]

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

# Must stay a single worker: run state, proxy pool and WebSockets are in-process.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
