import asyncio
import asyncpg
from db.config import DB_CONFIG

async def delete_duplicate():
    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        print("=" * 80)
        print("DELETING DUPLICATE PROPERTY: 171641786")
        print("=" * 80)

        # Get both copies
        details = await conn.fetch("""
            SELECT id, property_id, price, bedrooms, address_id, created_at
            FROM properties
            WHERE property_id = '171641786'
            ORDER BY created_at
        """)

        if len(details) != 2:
            print(f"\n[ERROR] Expected 2 copies, found {len(details)}")
            return

        older_id = details[0]['id']
        newer_id = details[1]['id']

        print(f"\nOlder copy (will be DELETED):")
        print(f"  DB id: {older_id}")
        print(f"  Created: {details[0]['created_at']}")

        print(f"\nNewer copy (will be KEPT):")
        print(f"  DB id: {newer_id}")
        print(f"  Created: {details[1]['created_at']}")

        # Delete the older copy
        print(f"\nDeleting older copy...")
        await conn.execute("""
            DELETE FROM properties
            WHERE id = $1
        """, older_id)

        print(f"[OK] Deleted property DB id={older_id}")

        # Verify
        remaining = await conn.fetchval("""
            SELECT COUNT(*) FROM properties
            WHERE property_id = '171641786'
        """)

        print(f"\n[VERIFY] Properties with property_id='171641786': {remaining}")

        total = await conn.fetchval("SELECT COUNT(*) FROM properties")
        print(f"[VERIFY] Total properties in database: {total}")

        if total == 92:
            print("\n[SUCCESS] Database now has exactly 92 properties (20+20+52)")
        else:
            print(f"\n[WARNING] Expected 92 properties, but found {total}")

    except Exception as e:
        print(f"\n[ERROR] {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(delete_duplicate())
