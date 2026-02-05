# Database Documentation

## Overview

The Rightmove Property Scraper uses PostgreSQL with a **snapshot-based approach** to track property changes over time. This provides complete historical tracking without data loss.

## Prerequisites

1. **Install PostgreSQL**
   - Download from: https://www.postgresql.org/download/
   - Or use Docker: `docker run --name rightmove-db -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres`

2. **Create Database**
   ```sql
   CREATE DATABASE rightmove_scraper;
   ```

## Configuration

Edit `.env` file in project root:

```bash
DB_HOST=localhost
DB_PORT=5432
DB_NAME=rightmove_scraper
DB_USER=postgres
DB_PASSWORD=your_password
```

Or use Docker Compose (already configured):
```bash
docker-compose up -d postgres
```

## Snapshot Approach

The database uses **immutable snapshots** to track property history.

### How It Works

Each time the scraper runs:
- ✅ **New properties** → Creates first snapshot
- ✅ **Changed data** (price, status, offer_type, reduced_on) → Creates new snapshot
- ⏭️ **No changes** → Skips (no duplicate snapshot)

### Example

```
id (UUID)          | property_id | price     | status    | reduced_on   | created_at
-------------------|-------------|-----------|-----------|--------------|-------------------
abc-123-def        | 169356884   | 300000    | NULL      | NULL         | 2026-01-30 10:00
xyz-456-ghi        | 169356884   | 290000    | NULL      | 30/01/2026   | 2026-01-31 10:00  ← Price dropped
mno-789-pqr        | 169356884   | 290000    | SOLD STC  | 30/01/2026   | 2026-02-01 10:00  ← Status changed
```

### What Triggers a New Snapshot?

A new snapshot is created when **any** of these fields change:

- **price** - Property price change
- **status_id** - Status change (e.g., "For Sale" → "SOLD STC")
- **offer_type_id** - Offer type change (e.g., "Guide Price" → "Offers Over")
- **reduced_on** - Price reduction date change

## Database Schema

### Main Tables

**properties** - Immutable property snapshots
```sql
CREATE TABLE properties (
    id UUID PRIMARY KEY,
    property_id VARCHAR(50) NOT NULL,
    town_id INTEGER REFERENCES towns(id),
    offer_type_id INTEGER REFERENCES offer_types(id),
    property_type_id INTEGER REFERENCES property_types(id),
    status_id INTEGER REFERENCES statuses(id),
    county_id INTEGER REFERENCES counties(id),
    address_id INTEGER REFERENCES addresses(id),
    postcode_id INTEGER REFERENCES postcodes(id),
    url TEXT NOT NULL,
    price BIGINT,
    address_line1 TEXT,
    locality VARCHAR(100),
    full_address TEXT,
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    bedrooms VARCHAR(20),
    bathrooms VARCHAR(20),
    description TEXT,
    added_on VARCHAR(20),          -- Date property was listed
    reduced_on VARCHAR(20),        -- Date price was reduced
    size INTEGER,                  -- Property size (numeric value)
    tenure VARCHAR(50),            -- Freehold/Leasehold
    council_tax_band VARCHAR(10),  -- UK tax band (A-H)
    minio_images JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**places** - Hierarchical geographic structure
```sql
CREATE TABLE places (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    place_type TEXT CHECK (place_type IN ('county', 'town', 'locality', 'postcode')),
    parent_id INTEGER REFERENCES places(id) ON DELETE CASCADE,
    UNIQUE(name, place_type, parent_id)
);
```

**Normalized tables**:
- `postcodes` - Unique postcodes
- `counties` - Unique counties
- `towns` - Unique towns (backward compatibility)
- `offer_types` - Price qualifiers ("Offers in Region of", "Guide Price")
- `property_types` - Property types ("Detached", "Semi-Detached")
- `statuses` - Property statuses ("SOLD STC", "UNDER OFFER")
- `addresses` - Normalized addresses

## Query Examples

### 1. Track Price Changes

```sql
-- View price history for a property
SELECT price, status_id, reduced_on, created_at
FROM properties
WHERE property_id = '169356884'
ORDER BY created_at DESC;
```

### 2. Find Properties with Price Drops

```sql
-- Properties where price decreased
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

### 3. Monitor Status Changes

```sql
-- See when properties went to "SOLD STC"
SELECT p.property_id, p.full_address, p.price, s.name as status, p.created_at
FROM properties p
LEFT JOIN statuses s ON p.status_id = s.id
WHERE s.name LIKE '%SOLD%'
ORDER BY p.created_at DESC;
```

### 4. Get Latest State

```sql
-- Latest snapshot for each property
SELECT DISTINCT ON (property_id)
    property_id, price, full_address, bedrooms, bathrooms,
    size, council_tax_band, tenure, added_on, reduced_on
FROM properties
ORDER BY property_id, created_at DESC;
```

### 5. Filter by Property Features

```sql
-- Properties with specific criteria
SELECT DISTINCT ON (property_id) *
FROM properties
WHERE size > 1000
  AND council_tax_band IN ('C', 'D')
  AND bathrooms >= '2'
ORDER BY property_id, created_at DESC, price ASC;
```

### 6. Geographic Queries (Hierarchical)

```sql
-- All properties in Surrey county
WITH RECURSIVE place_tree AS (
    SELECT id FROM places WHERE name = 'Surrey' AND place_type = 'county'
    UNION ALL
    SELECT p.id FROM places p
    INNER JOIN place_tree pt ON p.parent_id = pt.id
)
SELECT DISTINCT ON (p.property_id) p.*
FROM properties p
WHERE p.postcode_id IN (
    SELECT id FROM places
    WHERE id IN (SELECT id FROM place_tree)
      AND place_type = 'postcode'
)
ORDER BY p.property_id, p.created_at DESC;
```

## Database Maintenance

### Check for Duplicate Snapshots

```bash
python check_snapshots.py
```

### Clean Up False Duplicates

```bash
python cleanup_duplicate_snapshots.py
```

### Verify Schema

```bash
python verify_new_fields.py
```

## Migration Scripts

Located in project root:

- `migrate_add_property_fields.py` - Add new property fields
- `migrate_size_to_integer.py` - Change size column to INTEGER
- `migrate_to_places_hierarchy.py` - Migrate to hierarchical places
- `cleanup_duplicate_snapshots.py` - Remove false duplicates

## Benefits

1. **Complete History** - Never lose data from updates
2. **Price Tracking** - See exactly when prices changed
3. **Status Tracking** - Know when properties sold
4. **Audit Trail** - Full record of all changes
5. **Efficient** - Only saves when data actually changes
6. **Queryable** - Rich querying with window functions
7. **Normalized** - No redundant data with hierarchical places

## Useful Files

- `db/queries.sql` - Useful SQL queries
- `db/normalized_queries.sql` - Queries using normalized tables
- `db/hierarchical_helpers.sql` - Helper functions for hierarchy
- `db/setup_database.sql` - Complete schema definition

## Tips

- Run scraper daily to track market changes
- Use provided SQL queries for analysis
- Old snapshots are kept forever (manual cleanup if needed)
- Each snapshot is immutable - never modified after creation
- Use `DISTINCT ON (property_id)` to get latest state
- Leverage window functions for price change analysis
