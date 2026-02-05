-- Normalized Database Queries (with Towns table)

-- ========================================
-- TOWNS MANAGEMENT
-- ========================================

-- View all towns
SELECT * FROM towns ORDER BY name;

-- Count properties per town
SELECT t.name, COUNT(DISTINCT p.property_id) as property_count
FROM towns t
LEFT JOIN properties p ON t.id = p.town_id
GROUP BY t.id, t.name
ORDER BY property_count DESC;

-- ========================================
-- LATEST SNAPSHOTS WITH TOWN
-- ========================================

-- View latest snapshot for all properties with town name
SELECT DISTINCT ON (p.property_id)
    p.property_id,
    t.name as town,
    p.address_line1,
    p.address_line2,
    p.postcode,
    p.price,
    p.status,
    p.bedrooms,
    p.property_type,
    p.created_at
FROM properties p
LEFT JOIN towns t ON p.town_id = t.id
ORDER BY p.property_id, p.created_at DESC;

-- ========================================
-- SEARCH BY TOWN
-- ========================================

-- Get all properties in a specific town (latest snapshots)
WITH latest AS (
    SELECT DISTINCT ON (property_id) *
    FROM properties
    ORDER BY property_id, created_at DESC
)
SELECT l.property_id, l.full_address, l.price, l.status, t.name as town
FROM latest l
JOIN towns t ON l.town_id = t.id
WHERE t.name = 'Epsom'
ORDER BY l.price;

-- ========================================
-- ADDRESS ANALYSIS
-- ========================================

-- Properties by postcode
SELECT postcode, COUNT(*) as count
FROM (
    SELECT DISTINCT ON (property_id) property_id, postcode
    FROM properties
    ORDER BY property_id, created_at DESC
) latest
WHERE postcode IS NOT NULL
GROUP BY postcode
ORDER BY count DESC;

-- View address components
SELECT
    property_id,
    address_line1,
    address_line2,
    postcode,
    full_address
FROM (
    SELECT DISTINCT ON (property_id) *
    FROM properties
    ORDER BY property_id, created_at DESC
) latest
LIMIT 10;

-- ========================================
-- PRICE TRACKING BY TOWN
-- ========================================

-- Average price per town (latest snapshots only)
WITH latest AS (
    SELECT DISTINCT ON (property_id) *
    FROM properties
    WHERE price IS NOT NULL
    ORDER BY property_id, created_at DESC
)
SELECT
    t.name as town,
    COUNT(*) as property_count,
    ROUND(AVG(l.price)) as avg_price,
    MIN(l.price) as min_price,
    MAX(l.price) as max_price
FROM latest l
JOIN towns t ON l.town_id = t.id
GROUP BY t.id, t.name
ORDER BY avg_price DESC;

-- ========================================
-- PRICE HISTORY BY TOWN
-- ========================================

-- View price changes for properties in a specific town
SELECT
    p.property_id,
    p.full_address,
    p.price,
    p.status,
    p.created_at,
    t.name as town
FROM properties p
JOIN towns t ON p.town_id = t.id
WHERE t.name = 'Epsom'
ORDER BY p.property_id, p.created_at DESC;

-- Properties with price changes in a specific town
SELECT
    p.property_id,
    t.name as town,
    COUNT(DISTINCT p.price) as price_changes,
    MIN(p.price) as lowest_price,
    MAX(p.price) as highest_price
FROM properties p
JOIN towns t ON p.town_id = t.id
WHERE t.name = 'Epsom' AND p.price IS NOT NULL
GROUP BY p.property_id, t.name
HAVING COUNT(DISTINCT p.price) > 1
ORDER BY price_changes DESC;

-- ========================================
-- REPORTS
-- ========================================

-- Comprehensive property report with town
WITH latest AS (
    SELECT DISTINCT ON (property_id) *
    FROM properties
    ORDER BY property_id, created_at DESC
)
SELECT
    l.property_id,
    t.name as town,
    l.address_line1 as street,
    l.postcode,
    l.price,
    l.status,
    l.bedrooms,
    l.property_type,
    l.images_count,
    l.scraped_at as last_scraped
FROM latest l
LEFT JOIN towns t ON l.town_id = t.id
ORDER BY t.name, l.price;

-- ========================================
-- COORDINATES & LOCATION
-- ========================================

-- View all properties with coordinates
SELECT
    property_id,
    full_address,
    latitude,
    longitude,
    price
FROM (
    SELECT DISTINCT ON (property_id) *
    FROM properties
    ORDER BY property_id, created_at DESC
) latest
WHERE latitude IS NOT NULL AND longitude IS NOT NULL;

-- Find properties near a specific location (within ~1km)
-- Example: Find properties near latitude 51.72749, longitude 0.45546
WITH latest AS (
    SELECT DISTINCT ON (property_id) *
    FROM properties
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    ORDER BY property_id, created_at DESC
)
SELECT
    property_id,
    full_address,
    price,
    latitude,
    longitude,
    -- Calculate approximate distance in km (simple Euclidean approximation)
    SQRT(
        POWER(69.1 * (latitude - 51.72749), 2) +
        POWER(69.1 * (longitude - 0.45546) * COS(latitude / 57.3), 2)
    ) * 1.609344 as distance_km
FROM latest
ORDER BY distance_km
LIMIT 10;

-- Properties grouped by approximate area (rounded coordinates)
SELECT
    ROUND(latitude::numeric, 2) as lat_area,
    ROUND(longitude::numeric, 2) as lon_area,
    COUNT(*) as property_count,
    ROUND(AVG(price)) as avg_price
FROM (
    SELECT DISTINCT ON (property_id) *
    FROM properties
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND price IS NOT NULL
    ORDER BY property_id, created_at DESC
) latest
GROUP BY lat_area, lon_area
HAVING COUNT(*) > 1
ORDER BY property_count DESC;

-- Export coordinates for mapping (CSV format)
-- Copy this result to create a CSV for Google Maps or other mapping tools
SELECT
    property_id,
    full_address,
    price,
    latitude,
    longitude,
    status
FROM (
    SELECT DISTINCT ON (property_id) *
    FROM properties
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    ORDER BY property_id, created_at DESC
) latest
ORDER BY price;

-- ========================================
-- CLEANUP
-- ========================================

-- Delete all properties from a specific town
-- DELETE FROM properties WHERE town_id = (SELECT id FROM towns WHERE name = 'Epsom');

-- Delete a town (will also delete associated properties due to CASCADE)
-- DELETE FROM towns WHERE name = 'Unknown';
