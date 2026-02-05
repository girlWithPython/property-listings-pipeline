import asyncio
import asyncpg
from db.config import DB_CONFIG

async def check():
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        # Get duplicate details
        details = await conn.fetch("""
            SELECT id, property_id, price, bedrooms, address_id, created_at, updated_at
            FROM properties
            WHERE property_id = '171641786'
            ORDER BY created_at
        """)

        print("\n" + "=" * 80)
        print("DUPLICATE PROPERTY: 171641786")
        print("=" * 80)

        for idx, prop in enumerate(details, 1):
            print(f"\nCopy {idx}:")
            print(f"  DB id: {prop['id']}")
            print(f"  Address ID: {prop['address_id']}")
            print(f"  Price: {prop['price']}")
            print(f"  Bedrooms: {prop['bedrooms']}")
            print(f"  Created: {prop['created_at']}")
            print(f"  Updated: {prop['updated_at']}")

        # Check if they have different addresses
        if len(details) == 2:
            if details[0]['address_id'] == details[1]['address_id']:
                print("\n[INFO] Both copies reference the SAME address_id")
                print("[ACTION] Should delete the older copy")
            else:
                print("\n[WARNING] Copies reference DIFFERENT address_ids")
                print("[ACTION] Need to investigate which is correct")

            # Get address details
            for idx, prop in enumerate(details, 1):
                addr = await conn.fetchrow("""
                    SELECT a.*, p.name as place_name, pc.name as postcode
                    FROM addresses a
                    LEFT JOIN places p ON a.place_id = p.id
                    LEFT JOIN places pc ON a.postcode_id = pc.id
                    WHERE a.id = $1
                """, prop['address_id'])

                print(f"\nCopy {idx} address:")
                print(f"  {addr['building']}, {addr['street']}")
                print(f"  {addr['place_name']}, {addr['postcode']}")

        # Check snapshots
        print("\n" + "=" * 80)
        print("SNAPSHOTS FOR BOTH COPIES")
        print("=" * 80)

        for idx, prop in enumerate(details, 1):
            snapshots = await conn.fetch("""
                SELECT snapshot_id, snapshot_date, price, status
                FROM property_snapshots
                WHERE property_id = $1
                ORDER BY snapshot_date DESC
            """, prop['id'])

            print(f"\nCopy {idx} (DB id={prop['id']}): {len(snapshots)} snapshot(s)")
            for snap in snapshots:
                print(f"  - {snap['snapshot_date']}: price={snap['price']}, status={snap['status']}")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(check())
