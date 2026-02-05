"""
Check addresses table for references to orphaned places
"""
import asyncio
import asyncpg
from db.config import DB_CONFIG


async def check():
    conn = await asyncpg.connect(**DB_CONFIG)

    print("=" * 80)
    print("CHECKING ADDRESSES REFERENCING ORPHANED PLACES")
    print("=" * 80)

    # Orphaned place IDs we identified
    orphaned_ids = [80, 99, 76]  # Epsom, Guildford, Stevenage

    for place_id in orphaned_ids:
        # Get place details
        place = await conn.fetchrow("""
            SELECT id, name, place_type, parent_id
            FROM places
            WHERE id = $1
        """, place_id)

        print(f"\n{place['name']} (ID: {place_id}, {place['place_type']}):")

        # Check addresses table
        addresses = await conn.fetch("""
            SELECT id, place_id, property_id
            FROM addresses
            WHERE place_id = $1
        """, place_id)

        if addresses:
            print(f"  Found {len(addresses)} address(es) referencing this place:")
            for addr in addresses[:5]:  # Show first 5
                print(f"    - Address ID: {addr['id']}, Property ID: {addr['property_id']}")

            # Check if these properties exist
            for addr in addresses[:3]:
                prop = await conn.fetchrow("""
                    SELECT property_id, full_address, town_id
                    FROM properties
                    WHERE property_id = $1
                """, addr['property_id'])

                if prop:
                    town_name = "NULL"
                    if prop['town_id']:
                        town = await conn.fetchrow("SELECT name FROM places WHERE id = $1", prop['town_id'])
                        if town:
                            town_name = town['name']

                    print(f"      Property {prop['property_id']}: town_id={prop['town_id']} ({town_name})")
                    print(f"        Address: {prop['full_address'][:60]}")
        else:
            print("  No addresses reference this place")

    # Check if there's a correct version of these places
    print("\n" + "=" * 80)
    print("CORRECT PLACE VERSIONS:")
    print("=" * 80)

    for town_name in ['Epsom', 'Guildford', 'Stevenage']:
        correct = await conn.fetch("""
            SELECT id, name, place_type, parent_id
            FROM places
            WHERE name = $1
            AND place_type = 'town'
            AND parent_id IS NOT NULL
        """, town_name)

        if correct:
            for c in correct:
                parent_name = "NULL"
                if c['parent_id']:
                    parent = await conn.fetchrow("SELECT name FROM places WHERE id = $1", c['parent_id'])
                    if parent:
                        parent_name = parent['name']

                print(f"\n{c['name']} (ID: {c['id']}):")
                print(f"  parent_id: {c['parent_id']} ({parent_name})")

                # Check how many addresses reference this correct version
                addr_count = await conn.fetchval("""
                    SELECT COUNT(*) FROM addresses WHERE place_id = $1
                """, c['id'])
                print(f"  Addresses: {addr_count}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(check())
