"""
Migration to consolidate duplicate places and addresses

Handles:
1. Duplicate addresses that would violate unique constraints
2. Updates remaining addresses to reference correct places
3. Deletes orphaned duplicates
"""
import asyncio
import asyncpg
from db.config import DB_CONFIG


# Mapping: orphaned_id -> correct_id
PLACE_MAPPING = {
    80: 24,  # Epsom (orphaned) -> Epsom (Surrey)
    99: 1,   # Guildford (orphaned) -> Guildford (Surrey)
    76: 27,  # Stevenage (orphaned) -> Stevenage (Hertfordshire)
}


async def migrate():
    conn = await asyncpg.connect(**DB_CONFIG)

    print("=" * 80)
    print("CONSOLIDATE DUPLICATE PLACES & ADDRESSES MIGRATION")
    print("=" * 80)

    try:
        # Step 1: Show current state
        print("\nStep 1: Current state...")

        for orphaned_id, correct_id in PLACE_MAPPING.items():
            orphaned = await conn.fetchrow("SELECT name FROM places WHERE id = $1", orphaned_id)
            orphaned_addrs = await conn.fetchval("SELECT COUNT(*) FROM addresses WHERE place_id = $1", orphaned_id)
            correct_addrs = await conn.fetchval("SELECT COUNT(*) FROM addresses WHERE place_id = $1", correct_id)

            print(f"  {orphaned['name']}: orphaned={orphaned_addrs} addrs, correct={correct_addrs} addrs")

        # Step 2: Handle duplicate addresses
        print("\nStep 2: Removing duplicate addresses...")

        total_deleted = 0

        for orphaned_id, correct_id in PLACE_MAPPING.items():
            # Find addresses that would create duplicates
            duplicates = await conn.fetch("""
                SELECT a_orphan.id
                FROM addresses a_orphan
                WHERE a_orphan.place_id = $1
                AND EXISTS (
                    SELECT 1
                    FROM addresses a_correct
                    WHERE a_correct.place_id = $2
                    AND (a_orphan.building, a_orphan.postcode_id) = (a_correct.building, a_correct.postcode_id)
                )
            """, orphaned_id, correct_id)

            if duplicates:
                place_name = await conn.fetchval("SELECT name FROM places WHERE id = $1", correct_id)
                print(f"  {place_name}: Found {len(duplicates)} duplicate address(es)")

                # Delete duplicates
                for dup in duplicates:
                    await conn.execute("DELETE FROM addresses WHERE id = $1", dup['id'])
                    total_deleted += 1

                print(f"    Deleted {len(duplicates)} duplicate addresses")

        print(f"  Total deleted: {total_deleted} duplicate addresses")

        # Step 3: Update remaining addresses to reference correct places
        print("\nStep 3: Updating remaining addresses...")

        for orphaned_id, correct_id in PLACE_MAPPING.items():
            result = await conn.execute("""
                UPDATE addresses
                SET place_id = $1
                WHERE place_id = $2
            """, correct_id, orphaned_id)

            count = int(result.split()[-1]) if result.split()[-1].isdigit() else 0
            if count > 0:
                place_name = await conn.fetchval("SELECT name FROM places WHERE id = $1", correct_id)
                print(f"  Updated {count} addresses for {place_name}")

        # Step 4: Handle postcodes linked to orphaned towns
        print("\nStep 4: Consolidating postcodes...")

        orphaned_postcode_ids = []

        for orphaned_town_id in [80, 99, 76]:
            postcodes = await conn.fetch("""
                SELECT id, name
                FROM places
                WHERE place_type = 'postcode'
                AND parent_id = $1
            """, orphaned_town_id)

            if not postcodes:
                continue

            correct_town_id = PLACE_MAPPING[orphaned_town_id]

            for pc in postcodes:
                # Check if this postcode exists under the correct town
                duplicate = await conn.fetchrow("""
                    SELECT id
                    FROM places
                    WHERE name = $1
                    AND place_type = 'postcode'
                    AND parent_id = $2
                """, pc['name'], correct_town_id)

                if duplicate:
                    # Move addresses from orphaned postcode to correct one
                    # First, delete duplicates
                    dup_addrs = await conn.fetch("""
                        SELECT a_orphan.id
                        FROM addresses a_orphan
                        WHERE a_orphan.postcode_id = $1
                        AND EXISTS (
                            SELECT 1
                            FROM addresses a_correct
                            WHERE a_correct.postcode_id = $2
                            AND (a_orphan.building, a_orphan.place_id) = (a_correct.building, a_correct.place_id)
                        )
                    """, pc['id'], duplicate['id'])

                    for da in dup_addrs:
                        await conn.execute("DELETE FROM addresses WHERE id = $1", da['id'])

                    # Then update remaining
                    result = await conn.execute("""
                        UPDATE addresses
                        SET postcode_id = $1
                        WHERE postcode_id = $2
                    """, duplicate['id'], pc['id'])

                    count = int(result.split()[-1]) if result.split()[-1].isdigit() else 0
                    if count > 0:
                        print(f"  Moved {count} addresses from postcode {pc['name']}")

                    orphaned_postcode_ids.append(pc['id'])
                else:
                    # No duplicate - just update parent_id
                    await conn.execute("""
                        UPDATE places
                        SET parent_id = $1
                        WHERE id = $2
                    """, correct_town_id, pc['id'])

        # Step 5: Delete orphaned postcodes
        if orphaned_postcode_ids:
            print(f"\nStep 5: Deleting {len(orphaned_postcode_ids)} orphaned postcodes...")

            for pc_id in orphaned_postcode_ids:
                await conn.execute("DELETE FROM places WHERE id = $1", pc_id)

        # Step 6: Delete orphaned towns
        print("\nStep 6: Deleting orphaned towns...")

        for orphaned_id in PLACE_MAPPING.keys():
            place_name = await conn.fetchval("SELECT name FROM places WHERE id = $1", orphaned_id)

            # Verify no references
            addr_count = await conn.fetchval("SELECT COUNT(*) FROM addresses WHERE place_id = $1", orphaned_id)
            child_count = await conn.fetchval("SELECT COUNT(*) FROM places WHERE parent_id = $1", orphaned_id)

            if addr_count == 0 and child_count == 0:
                await conn.execute("DELETE FROM places WHERE id = $1", orphaned_id)
                print(f"  Deleted: {place_name} (ID {orphaned_id})")
            else:
                print(f"  ! Cannot delete {place_name}: {addr_count} addrs, {child_count} children")

        # Step 7: Verify fix
        print("\nStep 7: Verification...")

        duplicates = await conn.fetch("""
            SELECT name, place_type, COUNT(*) as count
            FROM places
            GROUP BY name, place_type
            HAVING COUNT(*) > 1
        """)

        if duplicates:
            print(f"  ! {len(duplicates)} duplicate(s) remain:")
            for dup in duplicates:
                print(f"    - {dup['name']} ({dup['place_type']}): {dup['count']} entries")
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
