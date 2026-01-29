# Use a slim Python image as the base
FROM python:3.11-slim

# 1. Install EVERY system library required for Firefox/Camoufox + MySQL client
RUN apt-get update && apt-get install -y \
    libgtk-3-0 libnss3 libdbus-glib-1-2 libxt6 libxcomposite1 \
    libxdamage1 libxrandr2 libgbm1 libasound2 libpangocairo-1.0-0 \
    libpango-1.0-0 libcairo2 libatspi2.0-0 libatk1.0-0 \
    libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 \
    libxshmfence1 fonts-liberation wget xvfb \
    default-libmysqlclient-dev build-essential pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 3. Download the browser binaries during the BUILD phase
# This prevents the 713MB download from happening at runtime
RUN playwright install firefox
RUN playwright install-deps firefox

# 4. Copy your application code
COPY . .

# 5. Create necessary directories
RUN mkdir -p static/uploads

# 6. Set environment variables
ENV PYTHONUNBUFFERED=1

# 7. Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/api/health')" || exit 1

# 8. Start the app (using 1 worker for stability)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "app:app"]