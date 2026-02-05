"""Check addresses table schema"""
import asyncio
import asyncpg
from db.config import DB_CONFIG


async def check():
    conn = await asyncpg.connect(**DB_CONFIG)

    print("ADDRESSES TABLE SCHEMA:")
    cols = await conn.fetch("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'addresses'
        ORDER BY ordinal_position
    """)

    for c in cols:
        print(f"  {c['column_name']}: {c['data_type']}")

    print("\nSample rows:")
    rows = await conn.fetch("SELECT * FROM addresses LIMIT 5")
    for row in rows:
        print(f"  {dict(row)}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(check())
