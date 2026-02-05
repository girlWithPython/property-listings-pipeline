"""
Migration to remove duplicate orphaned places

Strategy:
1. Identify duplicates (same name, same place_type)
2. Keep the one with proper parent_id (not NULL)
3. Delete orphaned duplicates (parent_id IS NULL) that have no properties
"""
import asyncio
import asyncpg
from db.config import DB_CONFIG


async def migrate():
    conn = await asyncpg.connect(**DB_CONFIG)

    print("=" * 80)
    print("REMOVE DUPLICATE ORPHANED PLACES MIGRATION")
    print("=" * 80)

    try:
        # Step 1: Find duplicate places
        print("\nStep 1: Finding duplicate places...")

        duplicates = await conn.fetch("""
            SELECT name, place_type
            FROM places
            GROUP BY name, place_type
            HAVING COUNT(*) > 1
            ORDER BY name, place_type
        """)

        print(f"  Found {len(duplicates)} duplicate place name(s)")

        # Step 2: For each duplicate, identify orphaned entries
        print("\nStep 2: Identifying orphaned duplicates to remove...")

        orphaned_to_delete = []

        for dup in duplicates:
            entries = await conn.fetch("""
                SELECT id, name, place_type, parent_id
                FROM places
                WHERE name = $1 AND place_type = $2
                ORDER BY id
            """, dup['name'], dup['place_type'])

            # Count entries with and without parent_id
            with_parent = [e for e in entries if e['parent_id'] is not None]
            without_parent = [e for e in entries if e['parent_id'] is None]

            if with_parent and without_parent:
                # We have both - check if orphaned ones have no properties
                for orphan in without_parent:
                    # Check property references
                    prop_count = 0
                    if orphan['place_type'] == 'town':
                        prop_count = await conn.fetchval(
                            "SELECT COUNT(*) FROM properties WHERE town_id = $1",
                            orphan['id']
                        )
                    elif orphan['place_type'] == 'postcode':
                        prop_count = await conn.fetchval(
                            "SELECT COUNT(*) FROM properties WHERE postcode_id = $1",
                            orphan['id']
                        )

                    if prop_count == 0:
                        orphaned_to_delete.append({
                            'id': orphan['id'],
                            'name': orphan['name'],
                            'place_type': orphan['place_type'],
                            'parent_id': orphan['parent_id']
                        })
                        print(f"  - [{orphan['id']}] {orphan['name']} ({orphan['place_type']}) - 0 properties")
                    else:
                        print(f"  ! [{orphan['id']}] {orphan['name']} ({orphan['place_type']}) - {prop_count} properties (SKIP)")

        if not orphaned_to_delete:
            print("  No orphaned duplicates to delete!")
            return

        print(f"\n  Total to delete: {len(orphaned_to_delete)}")

        # Step 3: Delete orphaned duplicates
        print("\nStep 3: Deleting orphaned duplicates...")

        for orphan in orphaned_to_delete:
            # First, delete any child places (like postcodes under orphaned towns)
            if orphan['place_type'] == 'town':
                children = await conn.fetch("""
                    SELECT id, name, place_type
                    FROM places
                    WHERE parent_id = $1
                """, orphan['id'])

                for child in children:
                    # Check if child has properties
                    child_props = 0
                    if child['place_type'] == 'postcode':
                        child_props = await conn.fetchval(
                            "SELECT COUNT(*) FROM properties WHERE postcode_id = $1",
                            child['id']
                        )

                    if child_props == 0:
                        await conn.execute("DELETE FROM places WHERE id = $1", child['id'])
                        print(f"    Deleted child: [{child['id']}] {child['name']} ({child['place_type']})")
                    else:
                        print(f"    ! Skipped child with {child_props} properties: [{child['id']}] {child['name']}")

            # Delete the orphaned entry
            await conn.execute("DELETE FROM places WHERE id = $1", orphan['id'])
            print(f"  Deleted: [{orphan['id']}] {orphan['name']} ({orphan['place_type']})")

        # Step 4: Verify cleanup
        print("\nStep 4: Verifying cleanup...")

        remaining_duplicates = await conn.fetch("""
            SELECT name, place_type, COUNT(*) as count
            FROM places
            GROUP BY name, place_type
            HAVING COUNT(*) > 1
            ORDER BY name, place_type
        """)

        if remaining_duplicates:
            print(f"  ! Warning: {len(remaining_duplicates)} duplicate(s) still remain:")
            for dup in remaining_duplicates:
                print(f"    - {dup['name']} ({dup['place_type']}): {dup['count']} entries")
        else:
            print("  OK No duplicates remaining!")

        # Step 5: Check for orphaned towns
        print("\nStep 5: Checking for orphaned towns...")

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
