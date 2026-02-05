import asyncio
import asyncpg
from db.config import DB_CONFIG
from datetime import datetime, timedelta

async def check_recent_additions():
    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        print("=" * 80)
        print("RECENT PROPERTY ADDITIONS")
        print("=" * 80)

        # Get properties added in last 24 hours
        recent = await conn.fetch("""
            SELECT
                DATE(created_at) as date,
                COUNT(*) as count
            FROM properties
            WHERE created_at >= NOW() - INTERVAL '24 hours'
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """)

        print("\nProperties added in last 24 hours:")
        total_24h = 0
        for row in recent:
            print(f"  {row['date']}: {row['count']} properties")
            total_24h += row['count']
        print(f"\nTotal in last 24 hours: {total_24h}")

        # Get properties by town
        print("\n" + "=" * 80)
        print("PROPERTIES BY TOWN (Last 24 hours)")
        print("=" * 80)

        by_town = await conn.fetch("""
            SELECT
                t.name as town,
                COUNT(p.id) as count,
                MIN(p.created_at) as first_added,
                MAX(p.created_at) as last_added
            FROM properties p
            LEFT JOIN towns t ON p.town_id = t.id
            WHERE p.created_at >= NOW() - INTERVAL '24 hours'
            GROUP BY t.name
            ORDER BY count DESC
        """)

        for row in by_town:
            print(f"\n{row['town']}:")
            print(f"  Count: {row['count']}")
            print(f"  First: {row['first_added']}")
            print(f"  Last:  {row['last_added']}")

        # Check for Chelmsford specifically
        print("\n" + "=" * 80)
        print("CHELMSFORD PROPERTIES")
        print("=" * 80)

        chelmsford = await conn.fetch("""
            SELECT
                p.property_id,
                p.price,
                p.bedrooms,
                p.full_address,
                p.created_at
            FROM properties p
            LEFT JOIN towns t ON p.town_id = t.id
            WHERE t.name ILIKE '%chelmsford%'
            ORDER BY p.created_at DESC
            LIMIT 10
        """)

        if chelmsford:
            print(f"\nFound {len(chelmsford)} recent Chelmsford properties (showing last 10):")
            for prop in chelmsford:
                print(f"  {prop['property_id']}: {prop['bedrooms']}bed, £{prop['price']:,}")
                print(f"    Added: {prop['created_at']}")
        else:
            print("\n[WARNING] No Chelmsford properties found!")

        # Check total properties
        print("\n" + "=" * 80)
        print("OVERALL STATS")
        print("=" * 80)

        total = await conn.fetchval("SELECT COUNT(*) FROM properties")
        unique = await conn.fetchval("SELECT COUNT(DISTINCT property_id) FROM properties")

        print(f"Total property rows: {total}")
        print(f"Unique properties: {unique}")

        # Check all properties by date
        print("\n" + "=" * 80)
        print("PROPERTIES BY DATE (All time)")
        print("=" * 80)

        by_date = await conn.fetch("""
            SELECT
                DATE(created_at) as date,
                COUNT(*) as count
            FROM properties
            GROUP BY DATE(created_at)
            ORDER BY date DESC
            LIMIT 7
        """)

        for row in by_date:
            print(f"  {row['date']}: {row['count']} properties")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(check_recent_additions())
