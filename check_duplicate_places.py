"""
Check for duplicate places entries (same name, same place_type, different parent_id)
"""
import asyncio
import asyncpg
from db.config import DB_CONFIG


async def check():
    conn = await asyncpg.connect(**DB_CONFIG)

    print("=" * 80)
    print("CHECKING FOR DUPLICATE PLACES")
    print("=" * 80)

    # Find duplicate place names with different parent_ids
    duplicates = await conn.fetch("""
        SELECT name, place_type, COUNT(*) as count
        FROM places
        GROUP BY name, place_type
        HAVING COUNT(*) > 1
        ORDER BY name, place_type
    """)

    if duplicates:
        print(f"\nFound {len(duplicates)} place name(s) with duplicates:")

        for dup in duplicates:
            print(f"\n{dup['name']} ({dup['place_type']}) - {dup['count']} entries:")

            # Get all entries for this name/type
            entries = await conn.fetch("""
                SELECT id, name, place_type, parent_id
                FROM places
                WHERE name = $1 AND place_type = $2
                ORDER BY id
            """, dup['name'], dup['place_type'])

            for entry in entries:
                parent_name = "NULL"
                if entry['parent_id']:
                    parent = await conn.fetchrow("""
                        SELECT name, place_type FROM places WHERE id = $1
                    """, entry['parent_id'])
                    if parent:
                        parent_name = f"{parent['name']} ({parent['place_type']})"

                # Check how many properties reference this place
                prop_count = 0
                if entry['place_type'] == 'town':
                    prop_count = await conn.fetchval("""
                        SELECT COUNT(*) FROM properties WHERE town_id = $1
                    """, entry['id'])
                elif entry['place_type'] == 'postcode':
                    prop_count = await conn.fetchval("""
                        SELECT COUNT(*) FROM properties WHERE postcode_id = $1
                    """, entry['id'])

                print(f"  [ID: {entry['id']}] parent_id={entry['parent_id']} -> {parent_name}, {prop_count} properties")
    else:
        print("\nNo duplicates found!")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(check())
