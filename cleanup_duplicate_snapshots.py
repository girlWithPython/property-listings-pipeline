"""
Clean up false duplicate snapshots from the database

This script removes duplicate snapshots where all tracked fields are identical:
- price
- offer_type_id
- status_id
- reduced_on

For each group of identical snapshots, it keeps the oldest one and deletes the rest.
"""
import asyncio
import asyncpg
from db.config import DB_CONFIG


async def cleanup_duplicates():
    conn = await asyncpg.connect(**DB_CONFIG)

    print("=" * 80)
    print("DUPLICATE SNAPSHOT CLEANUP")
    print("=" * 80)

    try:
        # Find duplicate groups (same property_id and identical tracked fields)
        print("\nStep 1: Finding duplicate snapshot groups...")

        duplicates = await conn.fetch("""
            WITH snapshot_groups AS (
                SELECT
                    property_id,
                    price,
                    COALESCE(offer_type_id, 0) as offer_type_id,
                    COALESCE(status_id, 0) as status_id,
                    COALESCE(reduced_on, '') as reduced_on,
                    COUNT(*) as count,
                    (ARRAY_AGG(id ORDER BY created_at))[1] as keep_id,
                    ARRAY_AGG(id ORDER BY created_at) as all_ids
                FROM properties
                GROUP BY property_id, price, COALESCE(offer_type_id, 0),
                         COALESCE(status_id, 0), COALESCE(reduced_on, '')
                HAVING COUNT(*) > 1
            )
            SELECT
                property_id,
                count,
                keep_id,
                all_ids
            FROM snapshot_groups
            ORDER BY count DESC, property_id
        """)

        if not duplicates:
            print("\nNo duplicate snapshots found! Database is clean.")
            return

        print(f"\nFound {len(duplicates)} groups of duplicate snapshots:")

        total_to_delete = 0
        for dup in duplicates:
            duplicates_count = dup['count'] - 1  # Keep one, delete the rest
            total_to_delete += duplicates_count
            print(f"  - Property {dup['property_id']}: {dup['count']} identical snapshots "
                  f"({duplicates_count} to delete)")

        print(f"\nTotal snapshots to delete: {total_to_delete}")

        # Ask for confirmation
        print("\n" + "=" * 80)
        response = input("\nProceed with deletion? (yes/no): ").strip().lower()

        if response not in ['yes', 'y']:
            print("\nCleanup cancelled.")
            return

        # Delete duplicates
        print("\nStep 2: Deleting duplicate snapshots...")

        deleted_total = 0
        for dup in duplicates:
            keep_id = dup['keep_id']
            all_ids = dup['all_ids']

            # Delete all except the one we're keeping (first one chronologically)
            ids_to_delete = [id for id in all_ids if id != keep_id]

            if ids_to_delete:
                result = await conn.execute("""
                    DELETE FROM properties
                    WHERE id = ANY($1::uuid[])
                """, ids_to_delete)

                # Extract number from result string like "DELETE 2"
                deleted_count = int(result.split()[-1])
                deleted_total += deleted_count

                print(f"  Property {dup['property_id']}: Deleted {deleted_count} duplicates")

        print(f"\n" + "=" * 80)
        print(f"Cleanup completed successfully!")
        print(f"  Total snapshots deleted: {deleted_total}")

        # Show summary after cleanup
        print("\nStep 3: Verifying cleanup...")

        total_after = await conn.fetchval("SELECT COUNT(*) FROM properties")
        distinct_after = await conn.fetchval("SELECT COUNT(DISTINCT property_id) FROM properties")

        print(f"\nDatabase summary:")
        print(f"  Total snapshots: {total_after}")
        print(f"  Unique properties: {distinct_after}")

        # Check if any duplicates remain
        remaining_dups = await conn.fetchval("""
            WITH snapshot_groups AS (
                SELECT
                    property_id,
                    price,
                    COALESCE(offer_type_id, 0) as offer_type_id,
                    COALESCE(status_id, 0) as status_id,
                    COALESCE(reduced_on, '') as reduced_on,
                    COUNT(*) as count
                FROM properties
                GROUP BY property_id, price, COALESCE(offer_type_id, 0),
                         COALESCE(status_id, 0), COALESCE(reduced_on, '')
                HAVING COUNT(*) > 1
            )
            SELECT COUNT(*) FROM snapshot_groups
        """)

        if remaining_dups > 0:
            print(f"\nWarning: {remaining_dups} duplicate groups still remain")
            print("  (These may be legitimate snapshots from different time periods)")
        else:
            print(f"\nNo duplicate groups remain - database is clean!")

    except Exception as e:
        print(f"\nError during cleanup: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(cleanup_duplicates())
