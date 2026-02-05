"""
Simple migration: Just fix orphaned towns by setting their parent_id

This avoids complex consolidation and foreign key issues.
We simply link the orphaned towns to their proper counties.
"""
import asyncio
import asyncpg
from db.config import DB_CONFIG


# Town -> County mapping
TOWN_COUNTY_MAP = {
    'Epsom': 'Surrey',
    'Guildford': 'Surrey',
    'Stevenage': 'Hertfordshire',
}


async def migrate():
    conn = await asyncpg.connect(**DB_CONFIG)

    print("=" * 80)
    print("SIMPLE FIX FOR ORPHANED TOWNS")
    print("=" * 80)

    try:
        # Step 1: Find orphaned towns
        print("\nStep 1: Finding orphaned towns...")

        orphaned_towns = await conn.fetch("""
            SELECT id, name, place_type, parent_id
            FROM places
            WHERE place_type = 'town'
            AND parent_id IS NULL
            ORDER BY name
        """)

        if not orphaned_towns:
            print("  No orphaned towns found!")
            return

        print(f"  Found {len(orphaned_towns)} orphaned town(s):")
        for town in orphaned_towns:
            county = TOWN_COUNTY_MAP.get(town['name'], 'Unknown')
            print(f"    - {town['name']} (ID: {town['id']}) -> should be in {county}")

        # Step 2: Ensure counties exist
        print("\nStep 2: Ensuring county entries exist...")

        county_ids = {}
        for county_name in set(TOWN_COUNTY_MAP.values()):
            county_id = await conn.fetchval("""
                SELECT id FROM places
                WHERE place_type = 'county'
                AND name = $1
            """, county_name)

            if county_id:
                print(f"  OK {county_name} exists (ID: {county_id})")
                county_ids[county_name] = county_id
            else:
                county_id = await conn.fetchval("""
                    INSERT INTO places (name, place_type, parent_id)
                    VALUES ($1, 'county', NULL)
                    RETURNING id
                """, county_name)
                print(f"  + Created {county_name} (ID: {county_id})")
                county_ids[county_name] = county_id

        # Step 3: Link orphaned towns to counties
        print("\nStep 3: Linking orphaned towns to their counties...")

        for town in orphaned_towns:
            town_name = town['name']
            county_name = TOWN_COUNTY_MAP.get(town_name)

            if not county_name:
                print(f"  ! Unknown county for {town_name}, skipping")
                continue

            county_id = county_ids[county_name]

            await conn.execute("""
                UPDATE places
                SET parent_id = $1
                WHERE id = $2
            """, county_id, town['id'])

            print(f"  OK Linked {town_name} (ID {town['id']}) -> {county_name} (ID {county_id})")

        # Step 4: Verify fix
        print("\nStep 4: Verifying fix...")

        remaining_orphans = await conn.fetchval("""
            SELECT COUNT(*)
            FROM places
            WHERE place_type = 'town'
            AND parent_id IS NULL
        """)

        if remaining_orphans == 0:
            print("  OK No orphaned towns remaining!")
        else:
            print(f"  ! Warning: {remaining_orphans} orphaned town(s) still exist")

        # Step 5: Show summary
        print("\nStep 5: Town hierarchy summary...")

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
            print(f"  {town['town_name']} (ID {town['id']}) -> {county}: {town['address_count']} addresses")

        print("\n" + "=" * 80)
        print("MIGRATION COMPLETED SUCCESSFULLY")
        print("=" * 80)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())
