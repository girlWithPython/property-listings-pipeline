# Rightmove Property Scraper

A comprehensive property scraping and monitoring system for Rightmove.co.uk with automated geocoding, email notifications, and hierarchical location data.

## Features

- **Multi-URL Scraping**: Process multiple search criteria simultaneously
- **Snapshot-Based Tracking**: Historical price and status change tracking
- **Automated Reverse Geocoding**: Convert coordinates to UK postcodes, counties, and localities using Postcodes.io API
- **Email Notifications**: Automated alerts for new properties via SMTP (Outlook, Gmail, Yahoo)
- **Hierarchical Places**: Normalized geographic data structure (County → Town → Locality → Postcode)
- **Worker System**: Celery-based background task processing with Docker support
- **Image Storage**: MinIO S3-compatible storage for property images
- **Dual Coordinate System**: Rightmove approximate coordinates + precise postcode-based geocoding

## Architecture

### System Overview

```
┌─────────────────┐         ┌──────────────┐         ┌─────────────────┐
│   Playwright    │────────▶│  PostgreSQL  │◀────────│  Celery Workers │
│   Scraper       │         │   Database   │         │                 │
│                 │         │              │         │  - Scraper      │
│  - Multi-URL    │         │  - Properties│         │  - Geocoding    │
│  - Browser      │         │  - Snapshots │         │  - Email        │
│    automation   │         │  - Places    │         │  - Images       │
└─────────────────┘         └──────────────┘         └─────────────────┘
                                                               │
                            ┌──────────────┐                  │
                            │    MinIO     │◀─────────────────┘
                            │   (Images)   │
                            └──────────────┘
                                    │
                            ┌──────────────┐
                            │    Redis     │
                            │  (Broker)    │
                            └──────────────┘
```

### Database Schema

#### Core Tables

**properties** - Property snapshots (immutable history)
```sql
- id (UUID, PK)
- property_id (VARCHAR) - Rightmove property ID
- url (TEXT)
- price (BIGINT)
- full_address (TEXT)
- address_line1 (TEXT)
- locality (VARCHAR)
- bedrooms (VARCHAR)
- bathrooms (VARCHAR)
- description (TEXT)
- added_on (VARCHAR) - Date property was listed
- reduced_on (VARCHAR) - Date price was reduced
- size (INTEGER) - Property size in sq ft or sq m (numeric value only)
- council_tax_band (VARCHAR) - UK council tax band (A-H)
- latitude (DECIMAL), longitude (DECIMAL) - Coordinates from Rightmove
- minio_images (JSONB) - Array of image URLs in MinIO
- created_at (TIMESTAMP) - Snapshot timestamp

Foreign keys:
- address_id -> addresses(id)
- town_id -> towns(id)
- county_id -> counties(id)
- postcode_id -> postcodes(id)
- offer_type_id -> offer_types(id)
- property_type_id -> property_types(id)
- status_id -> statuses(id)
- tenure_id -> tenure_types(id)

UNIQUE constraint: None (allows multiple snapshots per property)
Indices: property_id, town_id, created_at
```

**addresses** - Normalized address storage
```sql
- id (SERIAL, PK)
- building (TEXT) - Building name/number
- street (TEXT)
- display_address (TEXT) - Full formatted address
- created_at (TIMESTAMP)

Foreign keys:
- place_id -> places(id) - Links to town/locality in hierarchy
- postcode_id -> postcodes(id)

UNIQUE constraint: (building, place_id, postcode_id)
Purpose: Deduplicates addresses across properties
```

**places** - Hierarchical geographic structure
```sql
- id (SERIAL, PK)
- name (TEXT)
- place_type (TEXT) - CHECK: county|town|locality|postcode
- parent_id (INTEGER) - Self-reference, REFERENCES places(id) ON DELETE CASCADE
- created_at (TIMESTAMP)

UNIQUE constraint: (name, place_type, parent_id)

Example hierarchy:
  Surrey (county, parent_id=NULL)
    ├── Guildford (town, parent_id=4)
    │   ├── Park Barn (locality, parent_id=1) [optional]
    │   │   └── GU2 8DD (postcode, parent_id=locality_id)
    │   └── GU1 1HZ (postcode, parent_id=1)
    └── Epsom (town, parent_id=4)
        └── KT19 9HL (postcode, parent_id=24)

Note: Hierarchy is automatically maintained by geocoding worker
Constraint ensures no duplicate places at same level
```

**postcodes** - Normalized postcode storage
```sql
- id (SERIAL, PK)
- postcode (VARCHAR, UNIQUE)
- created_at (TIMESTAMP)
```

**towns** - Town normalization
```sql
- id (SERIAL, PK)
- name (VARCHAR, UNIQUE)
- created_at (TIMESTAMP)
```

**counties** - County normalization
```sql
- id (SERIAL, PK)
- name (VARCHAR, UNIQUE)
- created_at (TIMESTAMP)
```

**tenure_types** - Tenure normalization (Freehold/Leasehold)
```sql
- id (SERIAL, PK)
- name (VARCHAR, UNIQUE)
- created_at (TIMESTAMP)
```

**offer_types** - Price qualifiers (e.g., "Offers in Region of")
```sql
- id (SERIAL, PK)
- name (VARCHAR, UNIQUE)
- created_at (TIMESTAMP)
```

**property_types** - Property type normalization
```sql
- id (SERIAL, PK)
- name (VARCHAR, UNIQUE) - e.g., "Detached", "Semi-Detached", "Terraced"
- created_at (TIMESTAMP)
```

**statuses** - Status normalization
```sql
- id (SERIAL, PK)
- name (VARCHAR, UNIQUE) - e.g., "For Sale", "SOLD STC", "Under Offer"
- created_at (TIMESTAMP)
```

#### Snapshot Approach

Each scrape creates a new record **only if data changed**:

```
Property 169356884:
  Snapshot 1 (2026-01-30): £300,000, status=NULL, reduced_on=NULL
  Snapshot 2 (2026-01-31): £290,000, status=NULL, reduced_on=31/01/2026  ← Price dropped & reduced_on changed
  Snapshot 3 (2026-02-01): £290,000, status=SOLD STC, reduced_on=31/01/2026  ← Status changed
```

**Tracked fields** (trigger new snapshot):
- Price changes
- Status changes (e.g., "For Sale" → "SOLD STC")
- Offer type changes (e.g., "Guide Price" → "Offers Over")
- Reduced on date changes (price reduction tracking)

Benefits:
- Complete audit trail of all changes
- Price history tracking
- Price reduction tracking
- No data loss from updates
- Efficient (only saves when data changes)

### Worker System

**Celery workers** handle background tasks:

1. **Scraper Worker** (`workers/scraper_tasks.py`)
   - Runs scraping as background task in Docker container
   - Uses Playwright in headless mode (no GUI required)
   - Automatically triggers geocoding after completion
   - Supports scheduling with Celery Beat
   - Parallel image downloads to MinIO

2. **Geocoding Worker** (`workers/geocoding.py`)
   - Reverse geocoding using Postcodes.io API
   - Converts coordinates → full postcode + county + locality
   - Handles partial postcodes and unitary authorities
   - Deduplicates by coordinates (one API call per location)
   - **Automatically maintains hierarchical places table**

3. **Email Worker** (`workers/email_tasks.py`)
   - Sends notifications for new properties
   - Supports SMTP (Outlook, Gmail, Yahoo, Office 365)
   - HTML email templates with property details

**Docker Configuration** (`Dockerfile`):
- Based on Python 3.11-slim for efficiency
- Includes Playwright browser (Chromium) and dependencies
- Pre-installed system libraries for headless browser operation
- PYTHONPATH configured for module imports

### Image Storage

**MinIO** (S3-compatible) stores property images:
- Organized by property ID
- Automatic deduplication
- Public access via presigned URLs
- Docker-based deployment

## Quick Start

### Prerequisites

- Python 3.8+
- PostgreSQL 12+
- Docker & Docker Compose
- Redis (for workers)

### Installation

1. **Clone repository**
```bash
git clone <repository-url>
cd movePaser
```

2. **Install Python dependencies**
```bash
pip install -r requirements.txt
playwright install chromium
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your settings
```

4. **Start Docker services**
```bash
docker-compose up -d
```

This starts:
- PostgreSQL (port 5432)
- Redis (port 6379)
- MinIO (port 9000)
- Celery worker

5. **Initialize database**
```bash
python -c "import asyncio; from db.database import DatabaseConnector; from db.config import DB_CONFIG; async def init(): db = DatabaseConnector(); await db.connect(**DB_CONFIG); await db.init_schema(); await db.disconnect(); asyncio.run(init())"
```

### Configuration

#### Search URLs

Edit `scraper/search_urls.py`:

```python
SEARCH_URLS = [
    {
        "url": "https://www.rightmove.co.uk/property-for-sale/find.html?...",
        "enabled": True,
        "description": "Guildford - 3+ beds, max £400k"
    },
    {
        "url": "https://www.rightmove.co.uk/property-to-rent/find.html?...",
        "enabled": True,
        "description": "Reading - Rentals"
    },
]

MAX_PAGES = 50  # Maximum pages per search
```

#### Email (Optional)

Edit `.env`:

```bash
# Gmail (recommended - requires App Password)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your.email@gmail.com
SMTP_PASSWORD=your_gmail_app_password  # 16-character App Password
SMTP_USE_TLS=true
FROM_NAME=Rightmove Property Scraper
NOTIFICATION_EMAILS=recipient@gmail.com

# Alternative: Outlook/Hotmail (no App Password needed)
# SMTP_HOST=smtp-mail.outlook.com
# SMTP_PORT=587
# SMTP_USERNAME=your.email@outlook.com
# SMTP_PASSWORD=your_regular_password
```

**To get Gmail App Password:**
1. Enable 2-Step Verification: https://myaccount.google.com/security
2. Generate App Password: https://myaccount.google.com/apppasswords
3. Copy the 16-character password (no spaces)

## Usage

### Run Scraper Manually

```bash
python -m scraper.run
```

This will:
1. Scrape all enabled URLs
2. Save properties to database
3. Download images to MinIO
4. Show statistics

### Run Scraper via Worker (Recommended)

```bash
# Trigger scraper (auto-triggers geocoding)
python trigger_scraper.py

# Check status
python trigger_scraper.py --status <task_id>

# Monitor logs
docker logs rightmove_worker --follow
```

Automated workflow:
```
1. Scraper runs → Saves properties
2. Auto-triggers reverse geocoding
3. Updates postcodes, counties, localities
4. All done automatically!
```

### Reverse Geocoding

**Automatic** (when using worker):
- Triggered automatically after scraping
- Processes all properties with coordinates
- Updates postcode, county, locality fields

**Manual**:
```bash
python trigger_geocoding.py
```

### Email Notifications

```bash
# Send notification for properties from last 24 hours
python trigger_email_notification.py --minutes 1440

# Check task status
python trigger_email_notification.py --status <task_id>
```

### Query Database

```bash
# Show latest properties
python show_final_state.py

# Check places hierarchy
python check_places.py

# Check coordinates
python check_coordinates_db.py

# Check for duplicate snapshots
python check_snapshots.py

# Clean up duplicate snapshots (if any)
python cleanup_duplicate_snapshots.py
```

## Common Workflows

### Daily Automated Scraping

1. **Configure Celery Beat** in `workers/celery_app.py`:
```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    'daily-scrape': {
        'task': 'workers.scraper_tasks.schedule_scraper',
        'schedule': crontab(hour=9, minute=0),  # 9 AM daily
    },
}
```

2. **Start Celery Beat**:
```bash
celery -A workers.celery_app beat --loglevel=info
```

### Price Drop Monitoring

Query properties with price changes:

```sql
WITH ranked AS (
    SELECT property_id, price, created_at, reduced_on,
           LAG(price) OVER (PARTITION BY property_id ORDER BY created_at) as prev_price
    FROM properties
)
SELECT DISTINCT property_id, price, prev_price, reduced_on, created_at
FROM ranked
WHERE price < prev_price
ORDER BY created_at DESC;
```

Query properties by council tax band and size:

```sql
SELECT DISTINCT ON (property_id)
    property_id, full_address, price, bathrooms, bedrooms,
    size, council_tax_band, tenure
FROM properties
WHERE council_tax_band IN ('C', 'D')
  AND size > 1000
ORDER BY property_id, created_at DESC;
```

Query recently added properties:

```sql
SELECT property_id, full_address, price, added_on, reduced_on
FROM properties
WHERE added_on >= '01/02/2026'
ORDER BY added_on DESC;
```

### Geographic Analysis

Find all properties in a county (using hierarchical structure):

```sql
WITH RECURSIVE place_tree AS (
    SELECT id FROM places WHERE name = 'Surrey' AND place_type = 'county'
    UNION ALL
    SELECT p.id FROM places p
    INNER JOIN place_tree pt ON p.parent_id = pt.id
)
SELECT DISTINCT ON (p.property_id) p.*
FROM properties p
WHERE p.postcode_id IN (
    SELECT id FROM places WHERE id IN (SELECT id FROM place_tree) AND place_type = 'postcode'
)
ORDER BY p.property_id, p.created_at DESC;
```

## Data Model

### Hierarchical Places

The system uses a normalized hierarchical structure for geographic data:

```
County (parent_id = NULL)
  └── Town (parent_id = County.id)
      └── Locality (parent_id = Town.id) [optional]
          └── Postcode (parent_id = Town.id or Locality.id)
```

Example:
```
Surrey (county)
  └── Guildford (town)
      ├── GU1 1HZ (postcode)
      ├── GU1 2UN (postcode)
      └── GU2 8DD (postcode)
```

Benefits:
- No data duplication
- Easy hierarchical queries
- Flexible geographic aggregation
- Proper referential integrity

## Project Structure

```
movePaser/
├── scraper/                 # Scraping logic
│   ├── run.py              # Main scraper entry point
│   ├── property_parser.py  # HTML parsing and extraction
│   ├── search_urls.py      # Search URL configuration
│   └── debug_html/         # Cached HTML for debugging
│
├── db/                      # Database layer
│   ├── database.py         # Connection and queries
│   ├── config.py           # Database configuration
│   ├── setup_database.sql  # Schema definition
│   └── queries.sql         # Useful SQL queries
│
├── workers/                 # Celery workers
│   ├── celery_app.py       # Celery configuration
│   ├── scraper_tasks.py    # Scraper worker
│   ├── geocoding.py        # Geocoding worker (Postcodes.io)
│   └── email_tasks.py      # Email worker (SMTP)
│
├── trigger_scraper.py       # CLI: Run scraper worker
├── trigger_geocoding.py     # CLI: Run geocoding worker
├── trigger_email_notification.py  # CLI: Send email
├── run_workers.py           # Start Celery workers
│
├── docker-compose.yml       # Docker services
├── Dockerfile               # Worker container
├── requirements.txt         # Python dependencies
└── .env                     # Configuration (not in git)
```

## API Integration

### Postcodes.io (Reverse Geocoding)

**Endpoint**: `https://api.postcodes.io/postcodes`

**Example Request**:
```
GET https://api.postcodes.io/postcodes?lat=51.3687&lon=-0.2757
```

**Response**:
```json
{
  "status": 200,
  "result": [{
    "postcode": "KT19 9PR",
    "admin_county": "Surrey",
    "admin_ward": "West Ewell"
  }]
}
```

**Features**:
- Free, no API key required
- Rate limit: ~600 requests/minute
- Handles unitary authorities (maps to ceremonial counties)
- Fallback for partial postcodes

## Troubleshooting

### Scraper Issues

**No properties found**:
- Check search URLs in `scraper/search_urls.py`
- Verify at least one URL has `enabled: True`
- Check Rightmove website is accessible

**Browser errors**:
```bash
playwright install chromium
```

### Database Issues

**Connection refused**:
```bash
# Check PostgreSQL is running
docker ps | grep postgres

# Check connection settings in .env
DB_HOST=localhost
DB_PORT=5432
```

**Schema not initialized**:
```bash
# Check if tables exist
psql -U postgres -d rightmove_scraper -c "\dt"

# Reinitialize schema
python -c "import asyncio; from db.database import DatabaseConnector; from db.config import DB_CONFIG; async def init(): db = DatabaseConnector(); await db.connect(**DB_CONFIG); await db.init_schema(); await db.disconnect(); asyncio.run(init())"
```

### Worker Issues

**Worker not processing tasks**:
```bash
# Check worker logs
docker logs rightmove_worker --tail 100

# Restart worker (note: use down/up to reload .env changes)
docker-compose down celery_worker && docker-compose up -d celery_worker

# Check Redis connection
redis-cli ping  # Should return PONG
```

**Scraper worker fails immediately**:
- Check if Playwright browsers are installed in container:
  ```bash
  docker exec rightmove_worker playwright --version
  ```
- If missing, rebuild container:
  ```bash
  docker-compose build celery_worker
  docker-compose up -d celery_worker
  ```
- Check logs for specific errors:
  ```bash
  docker logs rightmove_worker --follow
  ```

**ModuleNotFoundError in worker**:
- Ensure `PYTHONPATH=/app` is set in Dockerfile
- Rebuild container after Dockerfile changes:
  ```bash
  docker-compose build celery_worker
  docker-compose down celery_worker && docker-compose up -d celery_worker
  ```

**Geocoding fails**:
- Check internet connection (Postcodes.io API)
- Verify coordinates exist in database
- Check for partial postcodes (not supported by Postcodes.io)

### Email Issues

**Authentication failed (Gmail)**:
- **Enable 2-Step Verification** first: https://myaccount.google.com/security
- **Generate App Password**: https://myaccount.google.com/apppasswords
- Use the 16-character App Password (NOT your regular password)
- Remove spaces from the App Password when copying to `.env`
- Restart worker after updating: `docker-compose restart celery_worker`

**Authentication failed (Outlook)**:
- Some Outlook accounts have SMTP disabled by Microsoft
- Use full email as username
- Try `smtp.office365.com` instead of `smtp-mail.outlook.com`
- Or switch to Gmail with App Password

**No emails received**:
- Check spam/junk folder
- Verify `NOTIFICATION_EMAILS` in `.env`
- Check worker logs: `docker logs rightmove_worker --tail 50`
- Look for `[EMAIL-GMAIL] Sent to X recipients` confirmation

## Performance

### Scraping Speed
- ~2-3 properties/second
- ~100-150 properties/minute
- Parallel image downloads

### Database Queries
- Indexed on property_id, created_at, coordinates
- Snapshot queries use `DISTINCT ON` for latest data
- Hierarchical queries use recursive CTEs

### Worker Throughput
- Geocoding: ~10 locations/second (API rate limit)
- Email: Up to 300/day (Outlook), 500/day (Gmail)

## Security

- `.env` file in `.gitignore` (never committed)
- Database credentials in environment variables
- MinIO with access keys
- SMTP with TLS encryption
- No hardcoded secrets

## License

[MIT License](LICENSE.md)

## Contributing

1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Submit pull request

## Support

For issues and questions:
- Check documentation in project root
- Review troubleshooting section
- Check Docker logs for errors
- Verify configuration in `.env`
