"""
Show Stevenage hierarchical tree structure
"""
import asyncio
import asyncpg
from db.config import DB_CONFIG


async def show_tree():
    conn = await asyncpg.connect(**DB_CONFIG)

    print("=" * 80)
    print("STEVENAGE HIERARCHICAL TREE")
    print("=" * 80)

    # Get Hertfordshire county
    county = await conn.fetchrow("""
        SELECT id, name
        FROM places
        WHERE name = 'Hertfordshire' AND place_type = 'county'
    """)

    print(f"\n{county['name']} (county, ID {county['id']}, parent_id=NULL)")

    # Get Stevenage town
    town = await conn.fetchrow("""
        SELECT id, name
        FROM places
        WHERE name = 'Stevenage' AND place_type = 'town'
    """)

    if town:
        # Get parent ID
        town_parent = await conn.fetchval("SELECT parent_id FROM places WHERE id = $1", town['id'])
        print(f"  |- Stevenage (town, ID {town['id']}, parent_id={town_parent})")

        # Get all postcodes under Stevenage
        postcodes = await conn.fetch("""
            SELECT id, name, parent_id
            FROM places
            WHERE place_type = 'postcode'
            AND parent_id = $1
            ORDER BY name
        """, town['id'])

        print(f"     Total postcodes: {len(postcodes)}")

        for i, pc in enumerate(postcodes):
            is_last = (i == len(postcodes) - 1)
            prefix = "     |-" if not is_last else "     --"
            print(f"{prefix} {pc['name']} (postcode, ID {pc['id']}, parent_id={pc['parent_id']})")

    # Check for any orphaned SG postcodes
    orphaned = await conn.fetch("""
        SELECT id, name, parent_id
        FROM places
        WHERE place_type = 'postcode'
        AND name LIKE 'SG%'
        AND parent_id != $1
    """, town['id'])

    if orphaned:
        print(f"\n! WARNING: {len(orphaned)} SG postcodes NOT under Stevenage:")
        for pc in orphaned:
            parent_name = "NULL"
            if pc['parent_id']:
                parent = await conn.fetchrow("SELECT name, place_type FROM places WHERE id = $1", pc['parent_id'])
                if parent:
                    parent_name = f"{parent['name']} ({parent['place_type']})"
            print(f"  {pc['name']} -> parent_id={pc['parent_id']} ({parent_name})")
    else:
        print(f"\nOK All SG postcodes are correctly under Stevenage town")

    print("\n" + "=" * 80)

    await conn.close()


if __name__ == "__main__":
    asyncio.run(show_tree())
