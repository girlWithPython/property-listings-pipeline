import asyncio
import asyncpg
from db.config import DB_CONFIG

async def check_duplicates():
    print("=" * 80)
    print("CHECKING FOR DUPLICATE PROPERTIES")
    print("=" * 80)

    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        # Check total property count
        total = await conn.fetchval("SELECT COUNT(*) FROM properties")
        print(f"\nTotal properties in database: {total}")

        # Check for duplicate property_ids
        duplicates = await conn.fetch("""
            SELECT property_id, COUNT(*) as count
            FROM properties
            GROUP BY property_id
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)

        if duplicates:
            print(f"\n[WARNING] Found {len(duplicates)} duplicate property_id(s):")
            for dup in duplicates:
                print(f"  - Property ID {dup['property_id']}: {dup['count']} copies")

                # Show details of duplicates
                details = await conn.fetch("""
                    SELECT id, property_id, price, bedrooms, display_address, created_at, updated_at
                    FROM properties
                    WHERE property_id = $1
                    ORDER BY created_at
                """, dup['property_id'])

                for idx, prop in enumerate(details, 1):
                    print(f"    Copy {idx}: DB ID={prop['id']}, Price={prop['price']}, "
                          f"Bedrooms={prop['bedrooms']}, Created={prop['created_at']}, "
                          f"Updated={prop['updated_at']}")
        else:
            print("\n[OK] No duplicate property_ids found")

        # Check most recent properties
        print("\n" + "=" * 80)
        print("MOST RECENT 10 PROPERTIES")
        print("=" * 80)
        recent = await conn.fetch("""
            SELECT property_id, price, bedrooms, display_address, created_at, updated_at
            FROM properties
            ORDER BY updated_at DESC
            LIMIT 10
        """)

        for idx, prop in enumerate(recent, 1):
            print(f"{idx}. {prop['property_id']}: {prop['bedrooms']}bed, "
                  f"GBP{prop['price']:,}, {prop['display_address'][:50]}, "
                  f"Updated: {prop['updated_at']}")

        # Count properties by created_at date
        print("\n" + "=" * 80)
        print("PROPERTIES BY CREATION DATE")
        print("=" * 80)
        by_date = await conn.fetch("""
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM properties
            GROUP BY DATE(created_at)
            ORDER BY date DESC
            LIMIT 10
        """)

        for row in by_date:
            print(f"  {row['date']}: {row['count']} properties")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(check_duplicates())
