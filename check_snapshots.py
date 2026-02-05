"""
Check which properties have multiple snapshots and show what changed
"""
import asyncio
import asyncpg
from db.config import DB_CONFIG


async def check_snapshots():
    conn = await asyncpg.connect(**DB_CONFIG)

    # Get properties with multiple snapshots from recent scraper run
    print("=" * 80)
    print("PROPERTIES WITH MULTIPLE SNAPSHOTS")
    print("=" * 80)

    duplicates = await conn.fetch("""
        SELECT
            property_id,
            COUNT(*) as snapshot_count,
            MIN(created_at) as first_seen,
            MAX(created_at) as last_seen
        FROM properties
        WHERE created_at > NOW() - INTERVAL '1 hour'
        GROUP BY property_id
        HAVING COUNT(*) > 1
        ORDER BY snapshot_count DESC, property_id
    """)

    if not duplicates:
        print("\nNo properties with multiple snapshots found in last hour.")
        print("This means all properties were stable (no price/status changes).")
    else:
        print(f"\nFound {len(duplicates)} properties with multiple snapshots:\n")

        for dup in duplicates:
            print(f"\nProperty ID: {dup['property_id']}")
            print(f"  Snapshots: {dup['snapshot_count']}")
            print(f"  First seen: {dup['first_seen']}")
            print(f"  Last seen: {dup['last_seen']}")

            # Get all snapshots for this property
            snapshots = await conn.fetch("""
                SELECT
                    id,
                    price,
                    offer_type_id,
                    status_id,
                    reduced_on,
                    created_at
                FROM properties
                WHERE property_id = $1
                AND created_at > NOW() - INTERVAL '1 hour'
                ORDER BY created_at ASC
            """, dup['property_id'])

            print(f"\n  Snapshot history:")
            for i, snap in enumerate(snapshots, 1):
                print(f"    [{i}] {snap['created_at'].strftime('%H:%M:%S')} - "
                      f"Price: £{snap['price']:,} | "
                      f"Offer Type: {snap['offer_type_id']} | "
                      f"Status: {snap['status_id']} | "
                      f"Reduced On: {snap['reduced_on']}")

            # Show what changed
            if len(snapshots) >= 2:
                print(f"\n  Changes detected:")
                for i in range(1, len(snapshots)):
                    prev = snapshots[i-1]
                    curr = snapshots[i]

                    if prev['price'] != curr['price']:
                        print(f"    - Price changed: £{prev['price']:,} → £{curr['price']:,}")
                    if prev['offer_type_id'] != curr['offer_type_id']:
                        print(f"    - Offer type changed: {prev['offer_type_id']} → {curr['offer_type_id']}")
                    if prev['status_id'] != curr['status_id']:
                        print(f"    - Status changed: {prev['status_id']} → {curr['status_id']}")
                    if prev['reduced_on'] != curr['reduced_on']:
                        print(f"    - Reduced on changed: {prev['reduced_on']} → {curr['reduced_on']}")

    # Summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    total = await conn.fetchval("""
        SELECT COUNT(*) FROM properties
        WHERE created_at > NOW() - INTERVAL '1 hour'
    """)

    distinct = await conn.fetchval("""
        SELECT COUNT(DISTINCT property_id) FROM properties
        WHERE created_at > NOW() - INTERVAL '1 hour'
    """)

    print(f"\nTotal rows: {total}")
    print(f"Distinct properties: {distinct}")
    print(f"Extra snapshots (changes): {total - distinct}")

    if duplicates:
        print(f"\nProperties with changes: {len(duplicates)}")
        print(f"Change rate: {len(duplicates)/distinct*100:.1f}%")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(check_snapshots())
