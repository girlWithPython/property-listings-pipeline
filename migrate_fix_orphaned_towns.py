"""
Migration to fix orphaned towns in places table

Links towns to their proper county parents:
- Epsom -> Surrey
- Guildford -> Surrey
- Stevenage -> Hertfordshire
"""
import asyncio
import asyncpg
from db.config import DB_CONFIG


# Town -> County mapping (UK geographic data)
TOWN_COUNTY_MAP = {
    'Epsom': 'Surrey',
    'Guildford': 'Surrey',
    'Stevenage': 'Hertfordshire',
    'Woking': 'Surrey',
    'Reading': 'Berkshire',
}


async def migrate():
    conn = await asyncpg.connect(**DB_CONFIG)

    print("=" * 80)
    print("FIX ORPHANED TOWNS MIGRATION")
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
            print("  ! No orphaned towns found - all good!")
            return

        print(f"  Found {len(orphaned_towns)} orphaned towns:")
        for town in orphaned_towns:
            county = TOWN_COUNTY_MAP.get(town['name'], 'Unknown')
            print(f"    - {town['name']} (ID: {town['id']}) -> should be in {county}")

        # Step 2: Create/get county entries
        print("\nStep 2: Ensuring county entries exist...")

        for town in orphaned_towns:
            town_name = town['name']
            county_name = TOWN_COUNTY_MAP.get(town_name)

            if not county_name:
                print(f"  ! Unknown county for town: {town_name}")
                continue

            # Check if county exists in places table
            county_id = await conn.fetchval("""
                SELECT id FROM places
                WHERE place_type = 'county'
                AND name = $1
            """, county_name)

            if county_id:
                print(f"  OK County '{county_name}' exists (ID: {county_id})")
            else:
                # Create county entry (counties have no parent)
                county_id = await conn.fetchval("""
                    INSERT INTO places (name, place_type, parent_id)
                    VALUES ($1, 'county', NULL)
                    RETURNING id
                """, county_name)
                print(f"  + Created county '{county_name}' (ID: {county_id})")

        # Step 3: Link towns to counties
        print("\nStep 3: Linking towns to their counties...")

        for town in orphaned_towns:
            town_id = town['id']
            town_name = town['name']
            county_name = TOWN_COUNTY_MAP.get(town_name)

            if not county_name:
                continue

            # Get county ID
            county_id = await conn.fetchval("""
                SELECT id FROM places
                WHERE place_type = 'county'
                AND name = $1
            """, county_name)

            if not county_id:
                print(f"  ! Could not find county '{county_name}' for town '{town_name}'")
                continue

            # Update town's parent_id
            await conn.execute("""
                UPDATE places
                SET parent_id = $1
                WHERE id = $2
            """, county_id, town_id)

            print(f"  OK Linked '{town_name}' -> '{county_name}' (parent_id: {county_id})")

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
            print(f"  ! Warning: {remaining_orphans} orphaned towns still remain")

        # Step 5: Show updated hierarchy sample
        print("\nStep 5: Sample hierarchy:")

        sample = await conn.fetch("""
            SELECT
                t.id as town_id,
                t.name as town_name,
                c.id as county_id,
                c.name as county_name
            FROM places t
            LEFT JOIN places c ON t.parent_id = c.id
            WHERE t.place_type = 'town'
            ORDER BY t.name
            LIMIT 5
        """)

        for s in sample:
            county_name = s['county_name'] if s['county_name'] else 'NULL'
            print(f"  {s['town_name']} (town:{s['town_id']}) -> {county_name} (county:{s['county_id']})")

        print("\n" + "=" * 80)
        print("MIGRATION COMPLETED SUCCESSFULLY")
        print("=" * 80)

    except Exception as e:
        print(f"\nERROR Migration failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())
