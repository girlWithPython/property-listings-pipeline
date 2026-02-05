"""
Migration to fix postcodes pointing to wrong parent

Problem: Postcodes are pointing directly to counties instead of towns
Solution: Update parent_id to point to the correct town based on postcode prefix

Example:
  WRONG: SG1 1SE -> parent_id=53 (Hertfordshire county)
  RIGHT: SG1 1SE -> parent_id=27 (Stevenage town)
"""
import asyncio
import asyncpg
from db.config import DB_CONFIG


# Postcode prefix -> Town name mapping
POSTCODE_TOWN_MAP = {
    'SG': 'Stevenage',     # SG postcodes -> Stevenage
    'GU': 'Guildford',     # GU postcodes -> Guildford
    'KT': 'Epsom',         # KT postcodes -> Epsom (some might be Woking)
    'GU21': 'Woking',      # GU21 specifically -> Woking
    'GU22': 'Woking',      # GU22 specifically -> Woking
}


async def migrate():
    conn = await asyncpg.connect(**DB_CONFIG)

    print("=" * 80)
    print("FIX POSTCODE PARENT_ID MIGRATION")
    print("=" * 80)

    try:
        # Step 1: Find all postcodes with wrong parents
        print("\nStep 1: Finding postcodes with incorrect parents...")

        # Get all postcodes
        all_postcodes = await conn.fetch("""
            SELECT id, name, parent_id
            FROM places
            WHERE place_type = 'postcode'
            ORDER BY name
        """)

        print(f"  Total postcodes: {len(all_postcodes)}")

        # Check each one
        wrong_parents = []

        for pc in all_postcodes:
            # Determine expected town based on postcode prefix
            postcode = pc['name']
            expected_town = None

            # Check specific prefixes first (GU21, GU22 -> Woking)
            if postcode.startswith('GU21') or postcode.startswith('GU22'):
                expected_town = 'Woking'
            else:
                # Check general prefix (GU -> Guildford, SG -> Stevenage, etc.)
                for prefix, town in POSTCODE_TOWN_MAP.items():
                    if postcode.startswith(prefix) and len(prefix) <= 3:  # Ignore specific ones like GU21
                        expected_town = town
                        break

            if not expected_town:
                continue

            # Get expected town ID
            town_record = await conn.fetchrow("""
                SELECT id FROM places
                WHERE name = $1 AND place_type = 'town'
            """, expected_town)

            if not town_record:
                print(f"  ! Warning: Town '{expected_town}' not found for postcode {postcode}")
                continue

            # Check if parent_id is correct
            if pc['parent_id'] != town_record['id']:
                parent_name = "NULL"
                if pc['parent_id']:
                    parent = await conn.fetchrow("SELECT name, place_type FROM places WHERE id = $1", pc['parent_id'])
                    if parent:
                        parent_name = f"{parent['name']} ({parent['place_type']})"

                wrong_parents.append({
                    'id': pc['id'],
                    'name': postcode,
                    'current_parent_id': pc['parent_id'],
                    'current_parent_name': parent_name,
                    'expected_parent_id': town_record['id'],
                    'expected_parent_name': expected_town
                })

        print(f"  Postcodes with wrong parents: {len(wrong_parents)}")

        if not wrong_parents:
            print("  OK All postcodes have correct parents!")
            return

        # Step 2: Show what will be fixed
        print("\nStep 2: Postcodes to fix:")
        for wp in wrong_parents[:10]:  # Show first 10
            print(f"  {wp['name']}: parent_id={wp['current_parent_id']} ({wp['current_parent_name']}) -> {wp['expected_parent_id']} ({wp['expected_parent_name']})")

        if len(wrong_parents) > 10:
            print(f"  ... and {len(wrong_parents) - 10} more")

        # Step 3: Update postcodes
        print(f"\nStep 3: Updating {len(wrong_parents)} postcodes...")

        for wp in wrong_parents:
            await conn.execute("""
                UPDATE places
                SET parent_id = $1
                WHERE id = $2
            """, wp['expected_parent_id'], wp['id'])

            print(f"  OK {wp['name']} -> parent_id={wp['expected_parent_id']} ({wp['expected_parent_name']})")

        # Step 4: Verify fix
        print("\nStep 4: Verifying fix...")

        # Check each town
        for town_name in set(POSTCODE_TOWN_MAP.values()):
            town = await conn.fetchrow("""
                SELECT id FROM places
                WHERE name = $1 AND place_type = 'town'
            """, town_name)

            if not town:
                continue

            # Count postcodes under this town
            count = await conn.fetchval("""
                SELECT COUNT(*)
                FROM places
                WHERE place_type = 'postcode'
                AND parent_id = $1
            """, town['id'])

            print(f"  {town_name}: {count} postcodes")

        # Check for remaining wrong parents
        remaining = 0
        for pc in all_postcodes:
            postcode = pc['name']
            expected_town = None

            if postcode.startswith('GU21') or postcode.startswith('GU22'):
                expected_town = 'Woking'
            else:
                for prefix, town in POSTCODE_TOWN_MAP.items():
                    if postcode.startswith(prefix) and len(prefix) <= 3:
                        expected_town = town
                        break

            if expected_town:
                town_record = await conn.fetchrow("""
                    SELECT id FROM places
                    WHERE name = $1 AND place_type = 'town'
                """, expected_town)

                if town_record:
                    # Re-fetch current parent_id
                    current = await conn.fetchval("SELECT parent_id FROM places WHERE id = $1", pc['id'])
                    if current != town_record['id']:
                        remaining += 1

        if remaining == 0:
            print(f"\n  OK All postcodes have correct parents!")
        else:
            print(f"\n  ! Warning: {remaining} postcodes still have wrong parents")

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
