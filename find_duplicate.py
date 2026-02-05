import asyncio
import asyncpg
from db.config import DB_CONFIG

async def check():
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        # First, get the schema
        cols = await conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='properties'
            ORDER BY ordinal_position
        """)

        print("\nProperties table columns:")
        for c in cols:
            print(f"  - {c['column_name']}")

        # Get duplicate details
        print("\n" + "=" * 80)
        print("DUPLICATE PROPERTY: 171641786")
        print("=" * 80)

        details = await conn.fetch("""
            SELECT *
            FROM properties
            WHERE property_id = '171641786'
            ORDER BY created_at
        """)

        for idx, prop in enumerate(details, 1):
            print(f"\nCopy {idx}:")
            print(f"  DB id: {prop['id']}")
            print(f"  Property ID: {prop['property_id']}")
            print(f"  Price: {prop['price']}")
            print(f"  Bedrooms: {prop['bedrooms']}")
            print(f"  Address ID: {prop['address_id']}")
            print(f"  Created: {prop['created_at']}")

        # Recommendation
        if len(details) == 2:
            print("\n" + "=" * 80)
            print("RECOMMENDATION")
            print("=" * 80)
            if details[0]['address_id'] == details[1]['address_id']:
                print(f"Both copies share the same address_id ({details[0]['address_id']})")
                print(f"SAFE TO DELETE: Property DB id={details[0]['id']} (older copy)")
                print(f"KEEP: Property DB id={details[1]['id']} (newer copy)")
            else:
                print("Copies have DIFFERENT address_ids - manual review needed")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(check())
