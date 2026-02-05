# Dockerfile for Celery Worker
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Playwright and PostgreSQL
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    # Playwright dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (chromium only for efficiency)
RUN playwright install chromium

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app:$PYTHONPATH

# Default command: run celery worker listening to all queues
CMD ["celery", "-A", "workers.celery_app", "worker", "--loglevel=info", "--concurrency=4", "-Q", "celery,scraper,geocoding,email"]
