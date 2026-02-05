import asyncio
import asyncpg
from db.config import DB_CONFIG

async def check():
    conn = await asyncpg.connect(**DB_CONFIG)
    total = await conn.fetchval('SELECT COUNT(*) FROM properties')
    unique = await conn.fetchval('SELECT COUNT(DISTINCT property_id) FROM properties')

    print(f"Total property rows: {total}")
    print(f"Unique properties: {unique}")

    if total == unique:
        print("[OK] No duplicates found")
    else:
        print(f"[WARNING] {total - unique} duplicate(s) detected")

    await conn.close()

asyncio.run(check())
