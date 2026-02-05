"""
Check for towns in places table without parent_id
"""
import asyncio
import asyncpg
from db.config import DB_CONFIG


async def check():
    conn = await asyncpg.connect(**DB_CONFIG)

    print("=" * 80)
    print("CHECKING FOR ORPHANED TOWNS IN PLACES TABLE")
    print("=" * 80)

    # Find towns without parent_id
    orphaned_towns = await conn.fetch("""
        SELECT id, name, place_type, parent_id
        FROM places
        WHERE place_type = 'town'
        AND parent_id IS NULL
        ORDER BY name
    """)

    print(f"\nFound {len(orphaned_towns)} towns without parent_id:")
    for town in orphaned_towns:
        print(f"  [{town['id']}] {town['name']} (type: {town['place_type']}, parent: {town['parent_id']})")

    # Show hierarchical structure for comparison
    print("\n" + "=" * 80)
    print("EXAMPLE OF CORRECT HIERARCHICAL STRUCTURE:")
    print("=" * 80)

    example = await conn.fetch("""
        WITH RECURSIVE place_tree AS (
            -- Start with postcodes
            SELECT id, name, place_type, parent_id, 1 as level
            FROM places
            WHERE place_type = 'postcode'
            LIMIT 3

            UNION ALL

            -- Get parents recursively
            SELECT p.id, p.name, p.place_type, p.parent_id, pt.level + 1
            FROM places p
            INNER JOIN place_tree pt ON p.id = pt.parent_id
        )
        SELECT * FROM place_tree ORDER BY level DESC, name
    """)

    for ex in example:
        indent = "  " * (4 - ex['level'])
        print(f"{indent}[{ex['id']}] {ex['name']} ({ex['place_type']}) parent={ex['parent_id']}")

    # Check properties referencing orphaned towns
    if orphaned_towns:
        print("\n" + "=" * 80)
        print("PROPERTIES AFFECTED:")
        print("=" * 80)

        for town in orphaned_towns[:5]:  # Check first 5
            count = await conn.fetchval("""
                SELECT COUNT(*)
                FROM properties
                WHERE town_id = $1
            """, town['id'])

            if count > 0:
                print(f"\n  Town: {town['name']} (ID: {town['id']})")
                print(f"  Properties: {count}")

                # Show sample properties
                samples = await conn.fetch("""
                    SELECT property_id, full_address
                    FROM properties
                    WHERE town_id = $1
                    LIMIT 3
                """, town['id'])

                for sample in samples:
                    print(f"    - {sample['property_id']}: {sample['full_address'][:60]}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(check())
