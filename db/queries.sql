-- Database queries for rightmove_scraper (Snapshot Approach)

-- ========================================
-- LATEST SNAPSHOTS (Current State)
-- ========================================

-- View latest snapshot for all properties
SELECT DISTINCT ON (property_id)
    id, property_id, address, price, status, bedrooms, property_type,
    scraped_at, created_at
FROM properties
ORDER BY property_id, created_at DESC;

-- Count unique properties
SELECT COUNT(DISTINCT property_id) as unique_properties FROM properties;

-- Get latest snapshot for a specific property
SELECT * FROM properties
WHERE property_id = '169356884'
ORDER BY created_at DESC
LIMIT 1;

-- ========================================
-- PRICE TRACKING
-- ========================================

-- View full price history for a specific property
SELECT property_id, price, status, scraped_at, created_at
FROM properties
WHERE property_id = '169356884'
ORDER BY created_at DESC;

-- Find properties with price changes
SELECT property_id, COUNT(DISTINCT price) as price_count,
       MIN(price) as lowest_price, MAX(price) as highest_price
FROM properties
WHERE price IS NOT NULL
GROUP BY property_id
HAVING COUNT(DISTINCT price) > 1
ORDER BY price_count DESC;

-- Show price change timeline for a property
SELECT property_id, price, status,
       scraped_at,
       LAG(price) OVER (PARTITION BY property_id ORDER BY created_at) as previous_price,
       created_at
FROM properties
WHERE property_id = '169356884'
ORDER BY created_at DESC;

-- ========================================
-- STATUS TRACKING
-- ========================================

-- Find properties that changed to SOLD STC
SELECT DISTINCT ON (property_id)
    property_id, address, price, status, created_at
FROM properties
WHERE status LIKE '%SOLD%'
ORDER BY property_id, created_at DESC;

-- View status change history for a property
SELECT property_id, status, price, created_at
FROM properties
WHERE property_id = '169356884'
ORDER BY created_at DESC;

-- ========================================
-- STATISTICS
-- ========================================

-- Get average price from latest snapshots
WITH latest AS (
    SELECT DISTINCT ON (property_id) price
    FROM properties
    ORDER BY property_id, created_at DESC
)
SELECT AVG(CAST(REPLACE(REPLACE(price, '£', ''), ',', '') AS NUMERIC)) as avg_price
FROM latest
WHERE price IS NOT NULL;

-- Count snapshots per property
SELECT property_id, COUNT(*) as snapshot_count
FROM properties
GROUP BY property_id
ORDER BY snapshot_count DESC;

-- Properties scraped most recently
SELECT DISTINCT ON (property_id)
    property_id, address, price, scraped_at
FROM properties
ORDER BY property_id, scraped_at DESC;

-- ========================================
-- FILTERING (Latest Snapshots Only)
-- ========================================

-- Get properties by bedroom count (latest snapshot)
WITH latest AS (
    SELECT DISTINCT ON (property_id) *
    FROM properties
    ORDER BY property_id, created_at DESC
)
SELECT property_id, address, bedrooms, price
FROM latest
WHERE bedrooms = '3'
ORDER BY price;

-- Find properties by property type (latest snapshot)
WITH latest AS (
    SELECT DISTINCT ON (property_id) *
    FROM properties
    ORDER BY property_id, created_at DESC
)
SELECT property_id, address, property_type, price
FROM latest
WHERE property_type LIKE '%Terrace%'
ORDER BY price;

-- Properties with most images (latest snapshot)
WITH latest AS (
    SELECT DISTINCT ON (property_id) *
    FROM properties
    ORDER BY property_id, created_at DESC
)
SELECT property_id, address, images_count
FROM latest
ORDER BY images_count DESC
LIMIT 10;

-- ========================================
-- CLEANUP
-- ========================================

-- Delete all snapshots for a specific property
-- DELETE FROM properties WHERE property_id = '169356884';

-- Delete all properties (use with caution!)
-- DELETE FROM properties;

-- Drop the table (use with caution!)
-- DROP TABLE properties;
