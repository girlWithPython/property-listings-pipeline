"""
Migration to fix duplicate places by consolidating references

Strategy:
1. Identify duplicate places (same name, same place_type)
2. For each duplicate pair, keep the one with proper parent_id
3. Update all addresses/properties to reference the correct place
4. Delete orphaned duplicates
"""
import asyncio
import asyncpg
from db.config import DB_CONFIG


# Mapping: orphaned_id -> correct_id
PLACE_MAPPING = {
    80: 24,  # Epsom (orphaned) -> Epsom (Surrey)
    99: 1,   # Guildford (orphaned) -> Guildford (Surrey)
    76: 27,  # Stevenage (orphaned) -> Stevenage (Hertfordshire)
    # Postcodes will be handled separately
}


async def migrate():
    conn = await asyncpg.connect(**DB_CONFIG)

    print("=" * 80)
    print("FIX DUPLICATE PLACES MIGRATION")
    print("=" * 80)

    try:
        # Step 1: Show current state
        print("\nStep 1: Current duplicate state...")

        for orphaned_id, correct_id in PLACE_MAPPING.items():
            orphaned = await conn.fetchrow("SELECT name, place_type, parent_id FROM places WHERE id = $1", orphaned_id)
            correct = await conn.fetchrow("SELECT name, place_type, parent_id FROM places WHERE id = $1", correct_id)

            orphaned_addrs = await conn.fetchval("SELECT COUNT(*) FROM addresses WHERE place_id = $1", orphaned_id)
            correct_addrs = await conn.fetchval("SELECT COUNT(*) FROM addresses WHERE place_id = $1", correct_id)

            print(f"\n  {orphaned['name']} ({orphaned['place_type']}):")
            print(f"    Orphaned [ID {orphaned_id}]: parent={orphaned['parent_id']}, {orphaned_addrs} addresses")
            print(f"    Correct  [ID {correct_id}]: parent={correct['parent_id']}, {correct_addrs} addresses")

        # Step 2: Update addresses to reference correct places
        print("\nStep 2: Updating addresses to reference correct places...")

        for orphaned_id, correct_id in PLACE_MAPPING.items():
            # Update addresses.place_id
            result = await conn.execute("""
                UPDATE addresses
                SET place_id = $1
                WHERE place_id = $2
            """, correct_id, orphaned_id)

            count = int(result.split()[-1]) if result.split()[-1].isdigit() else 0
            place_name = await conn.fetchval("SELECT name FROM places WHERE id = $1", correct_id)
            print(f"  Updated {count} addresses: {place_name} [{orphaned_id}] -> [{correct_id}]")

        # Step 3: Handle postcodes linked to orphaned towns
        print("\nStep 3: Handling postcodes linked to orphaned towns...")

        # Find postcodes that are children of orphaned towns
        orphaned_postcode_ids = []
        for orphaned_town_id in [80, 99, 76]:
            postcodes = await conn.fetch("""
                SELECT id, name, parent_id
                FROM places
                WHERE place_type = 'postcode'
                AND parent_id = $1
            """, orphaned_town_id)

            for pc in postcodes:
                # Find if there's a duplicate postcode under the correct town
                correct_town_id = PLACE_MAPPING[orphaned_town_id]

                duplicate = await conn.fetchrow("""
                    SELECT id
                    FROM places
                    WHERE name = $1
                    AND place_type = 'postcode'
                    AND parent_id = $2
                """, pc['name'], correct_town_id)

                if duplicate:
                    # Update addresses from orphaned postcode to correct one
                    addr_count = await conn.execute("""
                        UPDATE addresses
                        SET postcode_id = $1
                        WHERE postcode_id = $2
                    """, duplicate['id'], pc['id'])

                    count = int(addr_count.split()[-1]) if addr_count.split()[-1].isdigit() else 0
                    print(f"  Updated {count} addresses: postcode {pc['name']} [{pc['id']}] -> [{duplicate['id']}]")

                    orphaned_postcode_ids.append(pc['id'])
                else:
                    # No duplicate - just update parent_id to correct town
                    await conn.execute("""
                        UPDATE places
                        SET parent_id = $1
                        WHERE id = $2
                    """, correct_town_id, pc['id'])

                    town_name = await conn.fetchval("SELECT name FROM places WHERE id = $1", correct_town_id)
                    print(f"  Updated postcode {pc['name']} parent: [{orphaned_town_id}] -> [{correct_town_id}] ({town_name})")

        # Step 4: Delete orphaned postcodes
        if orphaned_postcode_ids:
            print("\nStep 4: Deleting orphaned postcodes...")

            for pc_id in orphaned_postcode_ids:
                pc_name = await conn.fetchval("SELECT name FROM places WHERE id = $1", pc_id)
                await conn.execute("DELETE FROM places WHERE id = $1", pc_id)
                print(f"  Deleted postcode: {pc_name} (ID {pc_id})")
        else:
            print("\nStep 4: No orphaned postcodes to delete")

        # Step 5: Delete orphaned towns
        print("\nStep 5: Deleting orphaned towns...")

        for orphaned_id in PLACE_MAPPING.keys():
            place_name = await conn.fetchval("SELECT name FROM places WHERE id = $1", orphaned_id)

            # Verify no addresses reference it
            addr_count = await conn.fetchval("SELECT COUNT(*) FROM addresses WHERE place_id = $1", orphaned_id)
            child_count = await conn.fetchval("SELECT COUNT(*) FROM places WHERE parent_id = $1", orphaned_id)

            if addr_count == 0 and child_count == 0:
                await conn.execute("DELETE FROM places WHERE id = $1", orphaned_id)
                print(f"  Deleted: {place_name} (ID {orphaned_id})")
            else:
                print(f"  ! Skipped {place_name} (ID {orphaned_id}): {addr_count} addresses, {child_count} children")

        # Step 6: Verify fix
        print("\nStep 6: Verifying fix...")

        # Check for remaining duplicates
        duplicates = await conn.fetch("""
            SELECT name, place_type, COUNT(*) as count
            FROM places
            GROUP BY name, place_type
            HAVING COUNT(*) > 1
            ORDER BY name, place_type
        """)

        if duplicates:
            print(f"  ! Warning: {len(duplicates)} duplicate(s) still remain:")
            for dup in duplicates:
                print(f"    - {dup['name']} ({dup['place_type']}): {dup['count']} entries")
        else:
            print("  OK No duplicates remaining!")

        # Check for orphaned towns
        orphaned_towns = await conn.fetchval("""
            SELECT COUNT(*)
            FROM places
            WHERE place_type = 'town'
            AND parent_id IS NULL
        """)

        if orphaned_towns == 0:
            print("  OK No orphaned towns!")
        else:
            print(f"  ! Warning: {orphaned_towns} orphaned town(s) still exist")

        # Show summary
        print("\nStep 7: Summary of correct place hierarchy...")

        sample = await conn.fetch("""
            SELECT
                t.id as town_id,
                t.name as town_name,
                c.name as county_name,
                COUNT(DISTINCT a.id) as address_count
            FROM places t
            LEFT JOIN places c ON t.parent_id = c.id
            LEFT JOIN addresses a ON a.place_id = t.id
            WHERE t.place_type = 'town'
            GROUP BY t.id, t.name, c.name
            ORDER BY t.name
            LIMIT 10
        """)

        for s in sample:
            county = s['county_name'] if s['county_name'] else 'NULL'
            print(f"  {s['town_name']} (ID {s['town_id']}) -> {county}: {s['address_count']} addresses")

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
