"""
Verification script for places hierarchy fix
"""
import asyncio
import asyncpg
from db.config import DB_CONFIG


async def verify():
    conn = await asyncpg.connect(**DB_CONFIG)

    print("=" * 80)
    print("PLACES HIERARCHY VERIFICATION")
    print("=" * 80)

    # Check for orphaned towns
    orphaned_towns = await conn.fetchval("""
        SELECT COUNT(*)
        FROM places
        WHERE place_type = 'town'
        AND parent_id IS NULL
    """)

    print(f"\n1. Orphaned towns: {orphaned_towns}")

    # Check for duplicate places
    duplicates = await conn.fetch("""
        SELECT name, place_type, COUNT(*) as count
        FROM places
        GROUP BY name, place_type
        HAVING COUNT(*) > 1
        ORDER BY name
    """)

    print(f"\n2. Duplicate places: {len(duplicates)}")
    if duplicates:
        for dup in duplicates:
            print(f"   - {dup['name']} ({dup['place_type']}): {dup['count']} entries")

    # Show town hierarchy
    print(f"\n3. Town Hierarchy:")

    towns = await conn.fetch("""
        SELECT
            t.id,
            t.name as town_name,
            c.name as county_name,
            COUNT(DISTINCT a.id) as address_count
        FROM places t
        LEFT JOIN places c ON t.parent_id = c.id
        LEFT JOIN addresses a ON a.place_id = t.id
        WHERE t.place_type = 'town'
        GROUP BY t.id, t.name, c.name
        ORDER BY t.name
    """)

    for town in towns:
        county = town['county_name'] if town['county_name'] else 'NULL'
        print(f"   {town['town_name']} (ID {town['id']}) -> {county}: {town['address_count']} addresses")

    # Overall stats
    print(f"\n4. Overall Statistics:")

    total_places = await conn.fetchval("SELECT COUNT(*) FROM places")
    total_addresses = await conn.fetchval("SELECT COUNT(*) FROM addresses")
    total_properties = await conn.fetchval("SELECT COUNT(DISTINCT property_id) FROM properties")

    print(f"   Total places: {total_places}")
    print(f"   Total addresses: {total_addresses}")
    print(f"   Total properties: {total_properties}")

    print("\n" + "=" * 80)
    if orphaned_towns == 0 and len(duplicates) == 0:
        print("OK ALL CHECKS PASSED - HIERARCHY IS CLEAN")
    else:
        print("! ISSUES DETECTED")
    print("=" * 80)

    await conn.close()


if __name__ == "__main__":
    asyncio.run(verify())
