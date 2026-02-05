-- Hierarchical Places Helper Views and Functions
-- These make it easier to query the hierarchical structure

-- ============================================================================
-- VIEWS
-- ============================================================================

-- View: Complete address with full geographic hierarchy
CREATE OR REPLACE VIEW v_addresses_full AS
WITH RECURSIVE place_hierarchy AS (
    -- Start with the address's place
    SELECT
        a.id as address_id,
        p.id as place_id,
        p.name,
        p.place_type,
        p.parent_id,
        p.name as place_name,
        1 as level
    FROM addresses a
    LEFT JOIN places p ON a.place_id = p.id

    UNION ALL

    -- Recursively get parent places
    SELECT
        ph.address_id,
        p.id,
        p.name,
        p.place_type,
        p.parent_id,
        ph.place_name,
        ph.level + 1
    FROM places p
    INNER JOIN place_hierarchy ph ON p.id = ph.parent_id
)
SELECT DISTINCT ON (address_id)
    a.id as address_id,
    a.building,
    a.street,
    a.display_address,
    pc.postcode,
    -- Geographic hierarchy
    MAX(CASE WHEN place_type = 'locality' THEN name END) OVER (PARTITION BY a.id) as locality,
    MAX(CASE WHEN place_type = 'town' THEN name END) OVER (PARTITION BY a.id) as town,
    MAX(CASE WHEN place_type = 'county' THEN name END) OVER (PARTITION BY a.id) as county,
    -- IDs
    a.place_id,
    a.postcode_id
FROM addresses a
LEFT JOIN postcodes pc ON a.postcode_id = pc.id
LEFT JOIN place_hierarchy ph ON a.id = ph.address_id
ORDER BY address_id;

COMMENT ON VIEW v_addresses_full IS 'Complete addresses with flattened geographic hierarchy for easy querying';


-- View: Latest property snapshot with full address
CREATE OR REPLACE VIEW v_properties_latest AS
SELECT DISTINCT ON (p.property_id)
    p.property_id,
    p.url,
    p.price,
    p.bedrooms,
    p.property_type,
    p.status,
    p.latitude,
    p.longitude,
    p.created_at,
    -- Address details
    a.building,
    a.street,
    a.display_address,
    af.postcode,
    af.locality,
    af.town,
    af.county
FROM properties p
LEFT JOIN addresses a ON p.address_id = a.id
LEFT JOIN v_addresses_full af ON a.id = af.address_id
ORDER BY p.property_id, p.created_at DESC;

COMMENT ON VIEW v_properties_latest IS 'Latest snapshot of each property with complete address information';


-- View: Place hierarchy tree with full paths
CREATE OR REPLACE VIEW v_place_paths AS
WITH RECURSIVE place_tree AS (
    -- Leaf nodes (localities)
    SELECT
        id,
        name,
        place_type,
        parent_id,
        name as path,
        ARRAY[id] as id_path,
        1 as depth
    FROM places

    UNION ALL

    -- Recursively build paths upward
    SELECT
        pt.id,
        pt.name,
        pt.place_type,
        pt.parent_id,
        p.name || ' → ' || pt.path as path,
        p.id || pt.id_path,
        pt.depth + 1
    FROM places p
    INNER JOIN place_tree pt ON p.id = pt.parent_id
)
SELECT DISTINCT ON (id)
    id,
    name,
    place_type,
    parent_id,
    path,
    id_path,
    depth
FROM place_tree
ORDER BY id, depth DESC;

COMMENT ON VIEW v_place_paths IS 'Each place with its full hierarchical path (e.g., "Essex → Chelmsford → Springfield")';


-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Function: Get all descendant place IDs (children, grandchildren, etc.)
CREATE OR REPLACE FUNCTION get_descendant_places(place_id INTEGER)
RETURNS TABLE(descendant_id INTEGER) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE place_tree AS (
        -- Start with the given place
        SELECT id FROM places WHERE id = place_id

        UNION ALL

        -- Get all children
        SELECT p.id
        FROM places p
        INNER JOIN place_tree pt ON p.parent_id = pt.id
    )
    SELECT id FROM place_tree;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION get_descendant_places IS 'Returns all descendant place IDs for a given place (recursive)';


-- Function: Get all ancestor place IDs (parent, grandparent, etc.)
CREATE OR REPLACE FUNCTION get_ancestor_places(place_id INTEGER)
RETURNS TABLE(ancestor_id INTEGER, ancestor_name TEXT, ancestor_type TEXT, level INTEGER) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE place_tree AS (
        -- Start with the given place
        SELECT id, name, place_type, parent_id, 0 as level
        FROM places
        WHERE id = place_id

        UNION ALL

        -- Get all parents
        SELECT p.id, p.name, p.place_type, p.parent_id, pt.level + 1
        FROM places p
        INNER JOIN place_tree pt ON p.id = pt.parent_id
    )
    SELECT id, name, place_type, level FROM place_tree WHERE level > 0;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION get_ancestor_places IS 'Returns all ancestor places for a given place (parent, grandparent, etc.)';


-- Function: Get full path for a place
CREATE OR REPLACE FUNCTION get_place_path(place_id INTEGER)
RETURNS TEXT AS $$
DECLARE
    place_path TEXT;
BEGIN
    SELECT path INTO place_path
    FROM v_place_paths
    WHERE id = place_id;

    RETURN place_path;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION get_place_path IS 'Returns the full hierarchical path for a place (e.g., "Essex → Chelmsford → Springfield")';


-- Function: Find properties in a place and all its descendants
CREATE OR REPLACE FUNCTION get_properties_in_place(
    place_name TEXT,
    place_type TEXT DEFAULT NULL
)
RETURNS TABLE(
    property_id VARCHAR(50),
    price BIGINT,
    address TEXT,
    postcode TEXT,
    locality TEXT,
    town TEXT,
    county TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH target_place AS (
        SELECT id FROM places
        WHERE name = place_name
        AND (place_type IS NULL OR places.place_type = get_properties_in_place.place_type)
        LIMIT 1
    ),
    descendant_places AS (
        SELECT descendant_id as id FROM target_place, get_descendant_places(target_place.id)
    )
    SELECT DISTINCT ON (p.property_id)
        p.property_id,
        p.price,
        af.display_address,
        af.postcode,
        af.locality,
        af.town,
        af.county
    FROM properties p
    INNER JOIN addresses a ON p.address_id = a.id
    LEFT JOIN v_addresses_full af ON a.id = af.address_id
    WHERE a.place_id IN (SELECT id FROM descendant_places)
    ORDER BY p.property_id, p.created_at DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_properties_in_place IS 'Find all properties in a place and all its descendants (e.g., all properties in Essex)';


-- ============================================================================
-- USEFUL QUERIES (as commented examples)
-- ============================================================================

/*
-- Example 1: Get all properties in Essex (county)
SELECT * FROM get_properties_in_place('Essex', 'county');

-- Example 2: Get all properties in Chelmsford (town)
SELECT * FROM get_properties_in_place('Chelmsford', 'town');

-- Example 3: Get place hierarchy for place ID 5
SELECT * FROM get_ancestor_places(5);

-- Example 4: Get all descendant places of Essex
SELECT p.* FROM places p
WHERE p.id IN (SELECT descendant_id FROM get_descendant_places(
    (SELECT id FROM places WHERE name = 'Essex' AND place_type = 'county')
));

-- Example 5: Get latest properties with full addresses
SELECT
    property_id,
    price,
    display_address,
    locality || ', ' || town || ', ' || county as full_location,
    postcode
FROM v_properties_latest
WHERE price IS NOT NULL
ORDER BY created_at DESC
LIMIT 10;

-- Example 6: Count properties by county
SELECT
    county,
    COUNT(*) as property_count,
    ROUND(AVG(price)) as avg_price
FROM v_properties_latest
WHERE county IS NOT NULL
GROUP BY county
ORDER BY property_count DESC;

-- Example 7: Get complete hierarchy path for all localities
SELECT
    name as locality_name,
    path as full_path
FROM v_place_paths
WHERE place_type = 'locality'
ORDER BY path;

-- Example 8: Find all properties with same postcode
SELECT
    p.property_id,
    p.price,
    af.display_address,
    af.postcode
FROM properties p
INNER JOIN addresses a ON p.address_id = a.id
INNER JOIN v_addresses_full af ON a.id = af.address_id
WHERE af.postcode = 'CM3 1NZ'
ORDER BY p.created_at DESC;
*/

-- ============================================================================
-- INDEXES (ensure optimal performance)
-- ============================================================================

-- Already created in migration, but listed here for reference:
-- CREATE INDEX idx_places_parent_id ON places(parent_id);
-- CREATE INDEX idx_places_type ON places(place_type);
-- CREATE INDEX idx_places_name ON places(name);
-- CREATE INDEX idx_addresses_place_id ON addresses(place_id);
-- CREATE INDEX idx_addresses_postcode_id ON addresses(postcode_id);
-- CREATE INDEX idx_postcodes_postcode ON postcodes(postcode);
-- CREATE INDEX idx_properties_address_id ON properties(address_id);

-- ============================================================================
-- STATISTICS
-- ============================================================================

-- Analyze tables to update statistics for query planner
ANALYZE places;
ANALYZE postcodes;
ANALYZE addresses;
ANALYZE properties;

-- Show table sizes
SELECT
    'places' as table_name,
    COUNT(*) as row_count,
    pg_size_pretty(pg_total_relation_size('places')) as total_size
FROM places
UNION ALL
SELECT 'postcodes', COUNT(*), pg_size_pretty(pg_total_relation_size('postcodes'))
FROM postcodes
UNION ALL
SELECT 'addresses', COUNT(*), pg_size_pretty(pg_total_relation_size('addresses'))
FROM addresses;
