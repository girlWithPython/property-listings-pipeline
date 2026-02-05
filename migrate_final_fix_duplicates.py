"""
Final comprehensive migration to fix duplicate places

Steps:
1. Find duplicate addresses (same building+postcode, different place_id)
2. Update properties to use correct address_id
3. Delete duplicate addresses
4. Delete orphaned places and their child postcodes
"""
import asyncio
import asyncpg
from db.config import DB_CONFIG


# Mapping: orphaned place_id -> correct place_id
PLACE_MAPPING = {
    80: 24,  # Epsom (orphaned) -> Epsom (Surrey)
    99: 1,   # Guildford (orphaned) -> Guildford (Surrey)
    76: 27,  # Stevenage (orphaned) -> Stevenage (Hertfordshire)
}


async def migrate():
    conn = await asyncpg.connect(**DB_CONFIG)

    print("=" * 80)
    print("COMPREHENSIVE FIX FOR DUPLICATE PLACES")
    print("=" * 80)

    try:
        # Step 1: Analyze current state
        print("\nStep 1: Current state...")

        for orphaned_id, correct_id in PLACE_MAPPING.items():
            orphaned = await conn.fetchrow("SELECT name FROM places WHERE id = $1", orphaned_id)
            orphaned_addrs = await conn.fetchval("SELECT COUNT(*) FROM addresses WHERE place_id = $1", orphaned_id)
            correct_addrs = await conn.fetchval("SELECT COUNT(*) FROM addresses WHERE place_id = $1", correct_id)

            print(f"  {orphaned['name']}:")
            print(f"    Orphaned ID {orphaned_id}: {orphaned_addrs} addresses")
            print(f"    Correct  ID {correct_id}: {correct_addrs} addresses")

        # Step 2: Handle duplicate addresses
        print("\nStep 2: Processing duplicate addresses...")

        total_updated = 0
        total_deleted = 0

        for orphaned_id, correct_id in PLACE_MAPPING.items():
            # Find address pairs: (orphaned_address, correct_address) with same building+postcode
            pairs = await conn.fetch("""
                SELECT
                    a_orphan.id as orphaned_addr_id,
                    a_correct.id as correct_addr_id,
                    a_orphan.building,
                    a_orphan.postcode_id
                FROM addresses a_orphan
                INNER JOIN addresses a_correct ON (
                    a_orphan.building = a_correct.building
                    AND a_orphan.postcode_id = a_correct.postcode_id
                )
                WHERE a_orphan.place_id = $1
                AND a_correct.place_id = $2
            """, orphaned_id, correct_id)

            if pairs:
                place_name = await conn.fetchval("SELECT name FROM places WHERE id = $1", correct_id)
                print(f"\n  {place_name}: Found {len(pairs)} duplicate address pair(s)")

                for pair in pairs:
                    # Check if any properties use the orphaned address
                    props = await conn.fetch("""
                        SELECT id, property_id
                        FROM properties
                        WHERE address_id = $1
                    """, pair['orphaned_addr_id'])

                    if props:
                        print(f"    Address [{pair['orphaned_addr_id']}]: {len(props)} properties")

                        # Update properties to use correct address
                        for prop in props:
                            await conn.execute("""
                                UPDATE properties
                                SET address_id = $1
                                WHERE id = $2
                            """, pair['correct_addr_id'], prop['id'])
                            total_updated += 1

                        # Delete orphaned address
                        await conn.execute("DELETE FROM addresses WHERE id = $1", pair['orphaned_addr_id'])
                        total_deleted += 1

                print(f"    Updated {total_updated} properties, deleted {total_deleted} addresses")

        # Step 3: Handle remaining orphaned addresses (no duplicate)
        print("\nStep 3: Updating remaining orphaned addresses...")

        for orphaned_id, correct_id in PLACE_MAPPING.items():
            # Get orphaned addresses that don't have duplicates
            orphaned_addrs = await conn.fetch("""
                SELECT id, building, postcode_id
                FROM addresses
                WHERE place_id = $1
            """, orphaned_id)

            if orphaned_addrs:
                print(f"\n  Orphaned place ID {orphaned_id}: {len(orphaned_addrs)} remaining addresses")

                for addr in orphaned_addrs:
                    # Check if updating to correct_id would create a duplicate
                    duplicate_exists = await conn.fetchval("""
                        SELECT id FROM addresses
                        WHERE place_id = $1
                        AND building = $2
                        AND postcode_id = $3
                    """, correct_id, addr['building'], addr['postcode_id'])

                    if duplicate_exists:
                        # Move properties from this address to the duplicate
                        props_count = await conn.execute("""
                            UPDATE properties
                            SET address_id = $1
                            WHERE address_id = $2
                        """, duplicate_exists, addr['id'])

                        count = int(props_count.split()[-1]) if props_count.split()[-1].isdigit() else 0

                        # Delete this address
                        await conn.execute("DELETE FROM addresses WHERE id = $1", addr['id'])
                        print(f"    Moved {count} props, deleted addr [{addr['id']}]")
                    else:
                        # Just update place_id
                        await conn.execute("""
                            UPDATE addresses
                            SET place_id = $1
                            WHERE id = $2
                        """, correct_id, addr['id'])
                        print(f"    Updated addr [{addr['id']}] to correct place")

        # Step 4: Delete orphaned postcodes
        print("\nStep 4: Deleting orphaned postcodes...")

        for orphaned_id in PLACE_MAPPING.keys():
            postcodes = await conn.fetch("""
                SELECT id, name FROM places
                WHERE place_type = 'postcode' AND parent_id = $1
            """, orphaned_id)

            for pc in postcodes:
                # Postcodes in places table shouldn't have addresses referencing them
                # They reference postcodes table via postcode_id
                await conn.execute("DELETE FROM places WHERE id = $1", pc['id'])
                print(f"  Deleted postcode place: {pc['name']}")

        # Step 5: Delete orphaned towns
        print("\nStep 5: Deleting orphaned towns...")

        for orphaned_id in PLACE_MAPPING.keys():
            place_name = await conn.fetchval("SELECT name FROM places WHERE id = $1", orphaned_id)

            # Verify no references
            addr_count = await conn.fetchval("SELECT COUNT(*) FROM addresses WHERE place_id = $1", orphaned_id)
            child_count = await conn.fetchval("SELECT COUNT(*) FROM places WHERE parent_id = $1", orphaned_id)

            if addr_count == 0 and child_count == 0:
                await conn.execute("DELETE FROM places WHERE id = $1", orphaned_id)
                print(f"  Deleted: {place_name} (ID {orphaned_id})")
            else:
                print(f"  ! Cannot delete {place_name}: {addr_count} addrs, {child_count} children still exist")

        # Step 6: Verify fix
        print("\nStep 6: Verification...")

        duplicates = await conn.fetch("""
            SELECT name, place_type, COUNT(*) as count
            FROM places
            GROUP BY name, place_type
            HAVING COUNT(*) > 1
        """)

        if duplicates:
            print(f"  ! {len(duplicates)} duplicate(s) remain:")
            for dup in duplicates:
                entries = await conn.fetch("SELECT id, parent_id FROM places WHERE name = $1 AND place_type = $2", dup['name'], dup['place_type'])
                print(f"    - {dup['name']} ({dup['place_type']}): {dup['count']} entries")
                for e in entries:
                    addr_count = await conn.fetchval("SELECT COUNT(*) FROM addresses WHERE place_id = $1", e['id'])
                    print(f"      [ID {e['id']}] parent={e['parent_id']}, {addr_count} addresses")
        else:
            print("  OK No place duplicates!")

        orphaned_towns = await conn.fetchval("""
            SELECT COUNT(*) FROM places
            WHERE place_type = 'town' AND parent_id IS NULL
        """)

        print(f"  Orphaned towns: {orphaned_towns}")

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
