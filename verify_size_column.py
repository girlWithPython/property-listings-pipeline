"""Verify size column is INTEGER"""
import asyncio
import asyncpg
from db.config import DB_CONFIG


async def verify():
    conn = await asyncpg.connect(**DB_CONFIG)

    result = await conn.fetch("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name='properties' AND column_name='size'
    """)

    if result:
        print(f"\nColumn: {result[0]['column_name']}")
        print(f"Type: {result[0]['data_type']}")
    else:
        print("\nSize column not found!")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(verify())
