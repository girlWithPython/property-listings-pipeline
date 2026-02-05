"""Verify new property fields are in database"""
import asyncio
import asyncpg
from db.config import DB_CONFIG


async def verify():
    conn = await asyncpg.connect(**DB_CONFIG)

    cols = await conn.fetch("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name='properties'
        AND column_name IN ('bathrooms', 'added_on', 'reduced_on', 'size', 'tenure', 'council_tax_band')
        ORDER BY column_name
    """)

    print("\nNew columns in properties table:")
    for col in cols:
        print(f"  - {col['column_name']}: {col['data_type']}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(verify())
