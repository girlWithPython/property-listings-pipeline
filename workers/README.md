# Workers System

This directory contains Celery-based background workers for asynchronous task processing with Docker support.

## Architecture

```
┌─────────────────┐         ┌──────────────┐         ┌─────────────────┐
│  Trigger Script │────────▶│    Redis     │────────▶│  Celery Worker  │
│                 │         │   (Broker)   │         │   (Docker)      │
│ - trigger_      │         │              │         │                 │
│   scraper.py    │         │  - Task Queue│         │  - Scraper      │
│ - trigger_      │         │  - Results   │         │  - Geocoding    │
│   geocoding.py  │         │              │         │  - Email        │
│ - trigger_      │         │              │         │  - Images       │
│   email_        │         │              │         │                 │
│   notification  │         │              │         │                 │
└─────────────────┘         └──────────────┘         └─────────────────┘
                                                               │
                                                               ▼
                                                    ┌──────────────────┐
                                                    │   PostgreSQL     │
                                                    │                  │
                                                    │  - Properties    │
                                                    │  - Places        │
                                                    │  - Postcodes     │
                                                    └──────────────────┘
                                                               │
                                                               ▼
                                                    ┌──────────────────┐
                                                    │     MinIO        │
                                                    │                  │
                                                    │  - Images        │
                                                    └──────────────────┘
```

## Workers

### 1. Scraper Worker (`scraper_tasks.py`)
- **Queue:** `scraper`
- **Purpose:** Run Rightmove property scraping in Docker (headless mode)
- **Tasks:**
  - `run_scraper`: Scrape all enabled URLs, automatically triggers geocoding
  - `schedule_scraper`: Periodic task for Celery Beat
- **Features:**
  - Playwright browser in headless mode (Docker compatible)
  - Multi-URL support
  - Automatic geocoding on completion
  - Parallel image downloads to MinIO
  - Full pagination (scrapes all properties, not just first page)

### 2. Geocoding Worker (`geocoding.py`)
- **Queue:** `geocoding`
- **Purpose:** **Reverse geocoding** - convert coordinates to full UK addresses using Postcodes.io API
- **Tasks:**
  - `reverse_geocode_missing_postcodes`: Batch process all properties with coordinates but missing postcodes
  - `reverse_geocode_single`: Geocode a specific coordinate pair
- **Features:**
  - Converts coordinates → full postcode + county + locality
  - Deduplicates by coordinates (one API call per location)
  - Handles unitary authorities (maps to ceremonial counties)
  - Maintains hierarchical places structure automatically
  - Rate-limited to respect API limits (~600/min)
  - Fallback for partial postcodes

### 3. Email Worker (`email_tasks.py`)
- **Queue:** `email`
- **Purpose:** Send property notification emails via SMTP
- **Tasks:**
  - `send_new_snapshots_notification`: Email properties added in last N minutes
- **Features:**
  - Universal SMTP support (Gmail, Outlook, Yahoo, Office 365)
  - HTML email templates
  - Configurable recipients
  - Production-ready (Gmail with App Password)

### 4. Image Worker (`image_tasks.py`)
- **Queue:** `images`
- **Purpose:** Download property images to MinIO S3 storage
- **Tasks:**
  - `process_property_images`: Download images for a property
- **Features:**
  - Parallel downloads
  - Automatic deduplication
  - S3-compatible storage (MinIO)

## Docker Setup

### Quick Start

```bash
# Start all services (PostgreSQL, Redis, MinIO, Worker)
docker-compose up -d

# Check worker logs
docker logs rightmove_worker --follow

# Rebuild worker after code changes
docker-compose build celery_worker
docker-compose down celery_worker && docker-compose up -d celery_worker
```

### Container Details

**Worker Container:**
- **Image:** Python 3.11-slim
- **Includes:** Playwright Chromium + system dependencies
- **Environment:** PYTHONPATH=/app
- **Headless:** Browser runs without GUI

**Important:**
- Worker copies code during build (`COPY . .`)
- Must rebuild after changing Python files
- `.env` changes only require restart (down + up)

## Usage

### Trigger Scraper

```bash
# Scrape all enabled URLs (auto-triggers geocoding)
python trigger_scraper.py

# Check status
python trigger_scraper.py --status <task_id>

# Monitor logs
docker logs rightmove_worker --follow
```

### Trigger Geocoding

```bash
# Reverse geocode all properties with coordinates
python trigger_geocoding.py

# Check status
python trigger_geocoding.py --status <task_id>
```

### Send Email Notifications

```bash
# Send email for properties from last 24 hours
python trigger_email_notification.py --minutes 1440

# Send for last hour
python trigger_email_notification.py --minutes 60

# Check status
python trigger_email_notification.py --status <task_id>
```

### Purge All Tasks

```bash
# Remove all pending tasks from all queues
python purge_celery_tasks.py
```

## Configuration

### Environment Variables (`.env`)

```bash
# Database
DB_HOST=postgres
DB_PORT=5432
DB_NAME=rightmove_scraper
DB_USER=postgres
DB_PASSWORD=postgres

# Redis
REDIS_URL=redis://redis:6379/0

# Email (Gmail with App Password)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your.email@gmail.com
SMTP_PASSWORD=your_16_char_app_password
SMTP_USE_TLS=true
FROM_NAME=Rightmove Property Scraper
NOTIFICATION_EMAILS=recipient1@example.com,recipient2@example.com

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=rightmove-images
MINIO_SECURE=false
```

### Search URLs Configuration

Edit `scraper/search_urls.py`:

```python
SEARCH_URLS = [
    {
        "url": "https://www.rightmove.co.uk/property-for-sale/find.html?...",
        "enabled": True,
        "description": "Guildford - 3+ beds, max £400k"
    },
]

MAX_PAGES = 50  # Maximum pages per search
```

**After changing search URLs:**
```bash
docker-compose build celery_worker
docker-compose down celery_worker && docker-compose up -d celery_worker
```

## Scheduled Tasks (Celery Beat)

To run scraping automatically on a schedule:

### 1. Update `workers/celery_app.py`:

```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    'daily-scrape': {
        'task': 'workers.scraper_tasks.schedule_scraper',
        'schedule': crontab(hour=9, minute=0),  # 9 AM daily
    },
}
```

### 2. Start Celery Beat:

```bash
celery -A workers.celery_app beat --loglevel=info
```

## Monitoring

### Task Status

```bash
# Check task by ID
python trigger_scraper.py --status abc-123-def-456

# Check active tasks
celery -A workers.celery_app inspect active

# Check registered tasks
celery -A workers.celery_app inspect registered
```

### Redis Queue Monitoring

```bash
# Connect to Redis
docker exec -it rightmove_redis redis-cli

# Check queue lengths
LLEN scraper
LLEN geocoding
LLEN email

# View keys
KEYS *
```

### Docker Logs

```bash
# Worker logs
docker logs rightmove_worker --follow

# Last 100 lines
docker logs rightmove_worker --tail 100

# Specific container
docker logs rightmove_redis
docker logs rightmove_minio
```

### Flower (Web UI)

```bash
# Install Flower
pip install flower

# Start Flower
celery -A workers.celery_app flower

# Open http://localhost:5555
```

## Troubleshooting

### Worker Not Processing Tasks

**Check worker is running:**
```bash
docker ps | grep worker
```

**Check worker logs:**
```bash
docker logs rightmove_worker --tail 50
```

**Restart worker:**
```bash
docker-compose restart celery_worker
```

**Rebuild worker (after code changes):**
```bash
docker-compose build celery_worker
docker-compose down celery_worker && docker-compose up -d celery_worker
```

### Redis Connection Issues

```bash
# Check Redis is running
docker ps | grep redis

# Test Redis connection
docker exec rightmove_redis redis-cli ping
# Should return: PONG

# Check Redis keys
docker exec rightmove_redis redis-cli KEYS "*"
```

### Email Not Sending

**Gmail:**
- Must enable 2-Step Verification
- Generate App Password (16 characters)
- Use App Password in `.env`, not regular password
- Restart worker after `.env` changes: `docker-compose down celery_worker && docker-compose up -d celery_worker`

**Outlook:**
- Some accounts have SMTP disabled by Microsoft
- Try `smtp.office365.com` instead of `smtp-mail.outlook.com`
- Or switch to Gmail with App Password

**Check logs:**
```bash
docker logs rightmove_worker | grep EMAIL
```

### Scraper Issues

**Playwright browser not found:**
```bash
# Rebuild container (installs Playwright browsers)
docker-compose build celery_worker
docker-compose up -d celery_worker
```

**Module import errors:**
```bash
# Ensure PYTHONPATH is set in Dockerfile
ENV PYTHONPATH=/app
```

**Pagination not working:**
- Check search URLs don't have duplicate `&index=` parameters
- Increase wait times in `scraper/run.py` if pages load slowly

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker ps | grep postgres

# Test connection
python -c "import asyncio; from db.database import DatabaseConnector; from db.config import DB_CONFIG; db = DatabaseConnector(); asyncio.run(db.connect(**DB_CONFIG)); print('OK')"
```

## API Limits

### Postcodes.io
- **Free**: No API key required
- **Rate limit**: ~600 requests/minute
- **No usage limits**
- **Endpoint**: https://api.postcodes.io/postcodes

### SMTP Email
- **Gmail**: 500 emails/day
- **Outlook**: 300 emails/day
- **Office 365**: 10,000 emails/day

## Performance

### Scraping
- **Speed**: ~2-3 properties/second (detail extraction)
- **Pagination**: ~9 seconds per page (24 properties)
- **Throughput**: ~100-150 properties/minute
- **Parallel**: Supports multiple search URLs

### Geocoding
- **API calls**: ~10/second (Postcodes.io rate limit)
- **Deduplication**: ~3-5 properties per unique coordinate
- **Coverage**: ~100% of properties with coordinates

### Email
- **Delivery**: <5 seconds per email
- **Batch**: 50 properties per email

## Production Deployment

### Docker Compose (Recommended)

Already configured in `docker-compose.yml`:
```bash
# Start all services
docker-compose up -d

# Scale workers (if needed)
docker-compose up -d --scale celery_worker=3
```

### Environment-Specific Config

Create `.env.production`:
```bash
DB_HOST=production-db.example.com
REDIS_URL=redis://production-redis:6379/0
SMTP_HOST=smtp.gmail.com
# ... other production settings
```

Load with:
```bash
docker-compose --env-file .env.production up -d
```

## Files

- `celery_app.py` - Celery configuration
- `scraper_tasks.py` - Scraper worker tasks
- `geocoding.py` - Reverse geocoding worker
- `email_tasks.py` - Email notification worker
- `email_config.py` - Email configuration
- `image_tasks.py` - Image download worker
- `minio_config.py` - MinIO configuration

## Next Steps

1. **Set up scheduled scraping** - Configure Celery Beat for daily runs
2. **Monitor performance** - Set up Flower or custom monitoring
3. **Scale workers** - Run multiple workers for higher throughput
4. **Add alerting** - Email notifications for scraper failures
5. **Optimize** - Parallel scraping of multiple URLs
