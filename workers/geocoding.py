"""
Reverse geocoding worker tasks using Postcodes.io API
Logic: coordinates → postcode, county, locality
"""
import asyncio
import aiohttp
import re
import asyncpg
from workers.celery_app import app
from db.config import DB_CONFIG


# Mapping of unitary authorities to their ceremonial counties
UNITARY_TO_CEREMONIAL_COUNTY = {
    # Berkshire unitary authorities
    "Reading": "Berkshire",
    "Slough": "Berkshire",
    "West Berkshire": "Berkshire",
    "Wokingham": "Berkshire",
    "Bracknell Forest": "Berkshire",
    "Windsor and Maidenhead": "Berkshire",

    # Other common unitary authorities
    "Brighton and Hove": "East Sussex",
    "Bristol, City of": "Bristol",
    "Bath and North East Somerset": "Somerset",
    "North Somerset": "Somerset",
    "South Gloucestershire": "Gloucestershire",
    "Bournemouth, Christchurch and Poole": "Dorset",
    "Southampton": "Hampshire",
    "Portsmouth": "Hampshire",
    "Isle of Wight": "Isle of Wight",
    "Medway": "Kent",
    "Thurrock": "Essex",
    "Southend-on-Sea": "Essex",
    "Milton Keynes": "Buckinghamshire",
    "Bedford": "Bedfordshire",
    "Central Bedfordshire": "Bedfordshire",
    "Luton": "Bedfordshire",
    "Peterborough": "Cambridgeshire",
    "Plymouth": "Devon",
    "Torbay": "Devon",
    "Swindon": "Wiltshire",
    "Leicester": "Leicestershire",
    "Nottingham": "Nottinghamshire",
    "Derby": "Derbyshire",
    "Kingston upon Hull, City of": "East Riding of Yorkshire",
    "North East Lincolnshire": "Lincolnshire",
    "North Lincolnshire": "Lincolnshire",
    "York": "North Yorkshire",
    "Halton": "Cheshire",
    "Warrington": "Cheshire",
    "Blackburn with Darwen": "Lancashire",
    "Blackpool": "Lancashire",
    "Stoke-on-Trent": "Staffordshire",
    "Telford and Wrekin": "Shropshire",
    "Herefordshire, County of": "Herefordshire",
    "Rutland": "Rutland",
}


async def get_or_create_place(conn, name: str, place_type: str, parent_id: int = None) -> int:
    """
    Atomically get or create a place entry

    Prevents race conditions when multiple workers try to create the same place
    Uses ON CONFLICT to handle concurrent inserts gracefully

    Args:
        conn: Database connection
        name: Place name
        place_type: 'county', 'town', 'locality', or 'postcode'
        parent_id: Parent place ID (None for top-level counties)

    Returns:
        Place ID
    """
    # First, try to find existing entry
    place_id = await conn.fetchval("""
        SELECT id FROM places
        WHERE name = $1
        AND place_type = $2
        AND (
            (parent_id = $3) OR
            (parent_id IS NULL AND $3 IS NULL)
        )
    """, name, place_type, parent_id)

    if place_id:
        return place_id

    # Try to insert, handle conflict if another worker inserted it concurrently
    try:
        place_id = await conn.fetchval("""
            INSERT INTO places (name, place_type, parent_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (name, place_type, parent_id) DO NOTHING
            RETURNING id
        """, name, place_type, parent_id)

        if place_id:
            print(f"[GEOCODING] Created {place_type}: {name} (parent_id={parent_id})")
            return place_id
    except Exception as e:
        # If ON CONFLICT DO NOTHING returned nothing, another worker created it
        print(f"[GEOCODING] Conflict creating {place_type} {name}, fetching existing...")

    # Another worker created it between our check and insert, fetch it
    place_id = await conn.fetchval("""
        SELECT id FROM places
        WHERE name = $1
        AND place_type = $2
        AND (
            (parent_id = $3) OR
            (parent_id IS NULL AND $3 IS NULL)
        )
    """, name, place_type, parent_id)

    return place_id


def is_partial_postcode(postcode: str) -> bool:
    """
    Check if postcode is partial (outward code only)
    Examples:
        "KT19" -> True (partial)
        "KT19 9PR" -> False (full)
        "SW1A 1AA" -> False (full)
    """
    if not postcode:
        return True

    # Full UK postcode has format: outward_code + space + inward_code
    # Inward code is always 3 characters: digit + 2 letters
    full_postcode_pattern = r'^[A-Z]{1,2}\d{1,2}[A-Z]?\s\d[A-Z]{2}$'

    return not re.match(full_postcode_pattern, postcode.strip(), re.IGNORECASE)


async def reverse_geocode(latitude: float, longitude: float) -> dict:
    """
    Reverse geocode coordinates to get postcode details

    API: https://api.postcodes.io/postcodes?lat=51.3530900&lon=-0.26807

    Returns:
        {
            "postcode": "KT19 9PR",
            "admin_county": "Surrey",  # or admin_district for unitary authorities
            "admin_ward": "West Ewell"
        }
    """
    if not latitude or not longitude:
        return {"postcode": None, "admin_county": None, "admin_ward": None}

    try:
        url = f"https://api.postcodes.io/postcodes?lat={latitude}&lon={longitude}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()

                    if data.get('status') == 200 and data.get('result'):
                        results = data['result']

                        # API returns an array of nearest postcodes
                        # Take the first (closest) one
                        if results and len(results) > 0:
                            nearest = results[0]
                            # Get county with proper fallback:
                            # 1. Use admin_county if available (traditional counties)
                            # 2. If None, check if admin_district is a unitary authority and map to ceremonial county
                            # 3. Otherwise use admin_district as-is
                            admin_county = nearest.get('admin_county')
                            admin_district = nearest.get('admin_district')

                            if admin_county:
                                county = admin_county
                            elif admin_district in UNITARY_TO_CEREMONIAL_COUNTY:
                                county = UNITARY_TO_CEREMONIAL_COUNTY[admin_district]
                            else:
                                county = admin_district

                            return {
                                "postcode": nearest.get('postcode'),
                                "admin_county": county,
                                "admin_ward": nearest.get('admin_ward')
                            }
                else:
                    print(f"[GEOCODING] Failed for coordinates ({latitude}, {longitude}): HTTP {response.status}")

    except Exception as e:
        print(f"[GEOCODING] Error reverse geocoding ({latitude}, {longitude}): {e}")

    return {"postcode": None, "admin_county": None, "admin_ward": None}


@app.task(name='workers.geocoding.reverse_geocode_missing_postcodes')
def reverse_geocode_missing_postcodes():
    """
    Find all properties with coordinates but missing/partial postcodes and reverse geocode them.
    Uses coordinates to fetch: postcode, county, locality
    """
    async def _reverse_geocode():
        # Create database connection directly
        conn = await asyncpg.connect(**DB_CONFIG)

        try:
            async with conn.transaction():
                # Get properties with coordinates but missing geocoding data
                # (partial/null postcode OR null county_id)
                # We need to get distinct combinations to avoid redundant API calls
                properties = await conn.fetch("""
                    SELECT DISTINCT ON (latitude, longitude)
                        id, property_id, latitude, longitude, postcode_id, county_id
                    FROM properties
                    WHERE latitude IS NOT NULL
                      AND longitude IS NOT NULL
                    ORDER BY latitude, longitude, created_at DESC
                    LIMIT 100
                """)

                if not properties:
                    print("[GEOCODING] No properties with coordinates to process")
                    return {"geocoded": 0, "updated_properties": 0}

                # Get actual postcode values for properties with postcode_id
                postcode_map = {}
                postcode_ids = [p['postcode_id'] for p in properties if p['postcode_id']]
                if postcode_ids:
                    postcodes = await conn.fetch("""
                        SELECT id, postcode FROM postcodes WHERE id = ANY($1)
                    """, postcode_ids)
                    postcode_map = {p['id']: p['postcode'] for p in postcodes}

                # Filter for those needing geocoding
                # Process if: (1) partial/null postcode OR (2) null county_id
                to_geocode = []
                for prop in properties:
                    postcode_id = prop['postcode_id']
                    county_id = prop['county_id']

                    # Get actual postcode value
                    postcode_value = postcode_map.get(postcode_id) if postcode_id else None

                    # Need geocoding if:
                    # - Postcode is partial/null (need full postcode + county)
                    # - OR county is null (need county even if postcode is full)
                    needs_geocoding = is_partial_postcode(postcode_value) or county_id is None

                    if needs_geocoding:
                        to_geocode.append(prop)

                if not to_geocode:
                    print("[GEOCODING] All properties have full postcodes and county data")
                    return {"geocoded": 0, "updated_properties": 0}

                print(f"[GEOCODING] Found {len(to_geocode)} properties needing reverse geocoding")

                geocoded_count = 0
                updated_properties = 0

                for prop in to_geocode:
                    # Keep original DECIMAL values for UPDATE precision
                    latitude = prop['latitude']
                    longitude = prop['longitude']
                    property_id = prop['property_id']
                    existing_postcode_id = prop['postcode_id']
                    existing_county_id = prop['county_id']

                    # Reverse geocode the coordinates (convert to float for API)
                    details = await reverse_geocode(float(latitude), float(longitude))

                    if details['postcode']:
                        # Get or create postcode ID (if not already have one)
                        postcode_value = details['postcode']

                        # If we already have a postcode, keep it; otherwise use the geocoded one
                        if existing_postcode_id:
                            postcode_id = existing_postcode_id
                            print(f"[GEOCODING] {property_id}: Keeping existing postcode, adding county")
                        else:
                            postcode_id = await conn.fetchval(
                                "SELECT id FROM postcodes WHERE postcode = $1",
                                postcode_value.strip().upper()
                            )
                            if not postcode_id:
                                postcode_id = await conn.fetchval(
                                    "INSERT INTO postcodes (postcode) VALUES ($1) RETURNING id",
                                    postcode_value.strip().upper()
                                )

                        # Get or create county ID (if not already have one)
                        if existing_county_id:
                            county_id = existing_county_id
                        elif details['admin_county']:
                            county_id = await conn.fetchval(
                                "SELECT id FROM counties WHERE name = $1",
                                details['admin_county']
                            )
                            if not county_id:
                                county_id = await conn.fetchval(
                                    "INSERT INTO counties (name) VALUES ($1) RETURNING id",
                                    details['admin_county']
                                )
                        else:
                            county_id = None

                        # Also update hierarchical places table
                        if details['admin_county']:
                            # Get or create county in places table (atomic operation)
                            county_place_id = await get_or_create_place(
                                conn,
                                details['admin_county'],
                                'county',
                                parent_id=None
                            )

                            # Find which town this postcode should belong to
                            # Look for properties with these coordinates to find their town
                            town_for_postcode = await conn.fetchrow("""
                                SELECT DISTINCT t.id as town_id, t.name as town_name
                                FROM properties p
                                INNER JOIN towns t ON p.town_id = t.id
                                WHERE p.latitude = $1 AND p.longitude = $2
                                LIMIT 1
                            """, latitude, longitude)

                            if town_for_postcode:
                                # Get or create town in places table (atomic operation)
                                town_place_id = await get_or_create_place(
                                    conn,
                                    town_for_postcode['town_name'],
                                    'town',
                                    parent_id=county_place_id
                                )

                                # Get or create postcode with town as parent (atomic operation)
                                postcode_place_id = await get_or_create_place(
                                    conn,
                                    postcode_value.strip().upper(),
                                    'postcode',
                                    parent_id=town_place_id
                                )
                            else:
                                # No town found - postcode points directly to county
                                postcode_place_id = await get_or_create_place(
                                    conn,
                                    postcode_value.strip().upper(),
                                    'postcode',
                                    parent_id=county_place_id
                                )

                        # Update all properties with these exact coordinates
                        # Only update fields that are currently NULL
                        result = await conn.execute("""
                            UPDATE properties
                            SET postcode_id = COALESCE(postcode_id, $1),
                                county_id = COALESCE(county_id, $2),
                                locality = COALESCE(locality, $3)
                            WHERE latitude = $4
                              AND longitude = $5
                        """,
                            postcode_id,
                            county_id,
                            details['admin_ward'],
                            latitude,
                            longitude
                        )

                        rows_updated = int(result.split()[-1])
                        updated_properties += rows_updated
                        geocoded_count += 1

                        print(f"[GEOCODING] {property_id}: {details['postcode']} ({details['admin_county']}, {details['admin_ward']}) - {rows_updated} properties")
                    else:
                        print(f"[GEOCODING] Failed to reverse geocode: ({latitude}, {longitude})")

                    # Small delay to be nice to the API
                    await asyncio.sleep(0.1)

                print(f"[GEOCODING] Complete: {geocoded_count} locations geocoded, {updated_properties} properties updated")

                return {
                    "geocoded": geocoded_count,
                    "updated_properties": updated_properties
                }

        except Exception as e:
            print(f"[GEOCODING] Error: {e}")
            raise
        finally:
            # Close the database connection
            await conn.close()

    try:
        return asyncio.run(_reverse_geocode())
    except RuntimeError as e:
        if "This event loop is already running" in str(e):
            # If running inside an existing event loop (Celery), use nest_asyncio
            import nest_asyncio
            nest_asyncio.apply()
            return asyncio.run(_reverse_geocode())
        raise


@app.task(name='workers.geocoding.reverse_geocode_single')
def reverse_geocode_single(latitude: float, longitude: float):
    """
    Reverse geocode a single coordinate and update all matching properties.

    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
    """
    async def _reverse_geocode_single():
        # Create database connection directly
        conn = await asyncpg.connect(**DB_CONFIG)

        try:
            details = await reverse_geocode(latitude, longitude)

            if details['postcode']:
                async with conn.transaction():
                    # Get or create postcode ID
                    postcode_value = details['postcode']
                    postcode_id = await conn.fetchval(
                        "SELECT id FROM postcodes WHERE postcode = $1",
                        postcode_value.strip().upper()
                    )
                    if not postcode_id:
                        postcode_id = await conn.fetchval(
                            "INSERT INTO postcodes (postcode) VALUES ($1) RETURNING id",
                            postcode_value.strip().upper()
                        )

                    # Get or create county ID
                    county_id = None
                    if details['admin_county']:
                        county_id = await conn.fetchval(
                            "SELECT id FROM counties WHERE name = $1",
                            details['admin_county']
                        )
                        if not county_id:
                            county_id = await conn.fetchval(
                                "INSERT INTO counties (name) VALUES ($1) RETURNING id",
                                details['admin_county']
                            )

                    result = await conn.execute("""
                        UPDATE properties
                        SET postcode_id = COALESCE(postcode_id, $1),
                            county_id = COALESCE(county_id, $2),
                            locality = COALESCE(locality, $3)
                        WHERE latitude = $4
                          AND longitude = $5
                    """,
                        postcode_id,
                        county_id,
                        details['admin_ward'],
                        latitude,
                        longitude
                    )

                    rows_updated = int(result.split()[-1])

                    print(f"[GEOCODING] ({latitude}, {longitude}): Updated {rows_updated} properties")

                    return {
                        "latitude": latitude,
                        "longitude": longitude,
                        "postcode": details['postcode'],
                        "county": details['admin_county'],
                        "locality": details['admin_ward'],
                        "updated_properties": rows_updated
                    }
            else:
                print(f"[GEOCODING] Failed to reverse geocode: ({latitude}, {longitude})")
                return None

        except Exception as e:
            print(f"[GEOCODING] Error: {e}")
            raise
        finally:
            # Close the database connection
            await conn.close()

    try:
        return asyncio.run(_reverse_geocode_single())
    except RuntimeError as e:
        if "This event loop is already running" in str(e):
            # If running inside an existing event loop (Celery), use nest_asyncio
            import nest_asyncio
            nest_asyncio.apply()
            return asyncio.run(_reverse_geocode_single())
        raise


@app.task(name='workers.geocoding.schedule_reverse_geocoding')
def schedule_reverse_geocoding():
    """
    Periodic task to check for and reverse geocode properties with missing postcodes.
    Can be run via Celery Beat on a schedule.
    """
    print("[GEOCODING] Running scheduled reverse geocoding check...")
    result = reverse_geocode_missing_postcodes.delay()
    return result.id
