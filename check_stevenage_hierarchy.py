"""
Check Stevenage hierarchical structure
"""
import asyncio
import asyncpg
from db.config import DB_CONFIG


async def check():
    conn = await asyncpg.connect(**DB_CONFIG)

    print("=" * 80)
    print("STEVENAGE HIERARCHY CHECK")
    print("=" * 80)

    # Get Stevenage town
    stevenage = await conn.fetchrow("""
        SELECT id, name, place_type, parent_id
        FROM places
        WHERE name = 'Stevenage' AND place_type = 'town'
    """)

    if stevenage:
        print(f"\nStevenage (town):")
        print(f"  ID: {stevenage['id']}")
        print(f"  parent_id: {stevenage['parent_id']}")

        # Get parent (should be Hertfordshire county)
        if stevenage['parent_id']:
            parent = await conn.fetchrow("SELECT id, name, place_type FROM places WHERE id = $1", stevenage['parent_id'])
            print(f"  Parent: {parent['name']} ({parent['place_type']}, ID {parent['id']})")

    # Get postcodes that should belong to Stevenage
    print(f"\nPostcodes in Stevenage area:")
    postcodes = await conn.fetch("""
        SELECT id, name, place_type, parent_id
        FROM places
        WHERE place_type = 'postcode'
        AND name LIKE 'SG%'
        ORDER BY name
    """)

    for pc in postcodes:
        parent_info = "NULL"
        if pc['parent_id']:
            parent = await conn.fetchrow("SELECT name, place_type FROM places WHERE id = $1", pc['parent_id'])
            if parent:
                parent_info = f"{parent['name']} ({parent['place_type']}, ID {pc['parent_id']})"

        # Check if correct
        status = "OK" if pc['parent_id'] == stevenage['id'] else "WRONG"
        if pc['parent_id'] == stevenage['parent_id']:
            status = "WRONG - Points to county, should point to town"

        print(f"  [{pc['id']}] {pc['name']} -> parent_id={pc['parent_id']} ({parent_info}) [{status}]")

    # Expected vs Actual
    print(f"\n" + "=" * 80)
    print("EXPECTED HIERARCHY:")
    print("=" * 80)
    print(f"Hertfordshire (county, ID {stevenage['parent_id']}, parent_id=NULL)")
    print(f"  └── Stevenage (town, ID {stevenage['id']}, parent_id={stevenage['parent_id']})")
    print(f"      └── SG postcodes (postcode, parent_id={stevenage['id']}) <-- SHOULD BE THIS")

    # Count correct vs incorrect
    correct = await conn.fetchval("""
        SELECT COUNT(*) FROM places
        WHERE place_type = 'postcode'
        AND name LIKE 'SG%'
        AND parent_id = $1
    """, stevenage['id'])

    incorrect = await conn.fetchval("""
        SELECT COUNT(*) FROM places
        WHERE place_type = 'postcode'
        AND name LIKE 'SG%'
        AND parent_id = $1
    """, stevenage['parent_id'])

    print(f"\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    print(f"Correct postcodes (parent_id={stevenage['id']} pointing to Stevenage town): {correct}")
    print(f"Incorrect postcodes (parent_id={stevenage['parent_id']} pointing to Hertfordshire county): {incorrect}")

    if incorrect > 0:
        print(f"\n! WARNING: {incorrect} postcodes are incorrectly pointing to county instead of town!")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(check())
