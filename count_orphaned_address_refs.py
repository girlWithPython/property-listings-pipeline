"""Count addresses referencing orphaned places"""
import asyncio
import asyncpg
from db.config import DB_CONFIG


async def check():
    conn = await asyncpg.connect(**DB_CONFIG)

    print("Checking addresses referencing orphaned places:")

    for pid in [80, 99, 76]:
        place = await conn.fetchrow("SELECT name, place_type FROM places WHERE id = $1", pid)
        cnt = await conn.fetchval("SELECT COUNT(*) FROM addresses WHERE place_id = $1", pid)
        print(f"  {place['name']} (ID {pid}): {cnt} addresses")

        if cnt > 0:
            # Show sample addresses
            addrs = await conn.fetch("SELECT id, display_address FROM addresses WHERE place_id = $1 LIMIT 3", pid)
            for addr in addrs:
                print(f"    - [{addr['id']}] {addr['display_address']}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(check())
