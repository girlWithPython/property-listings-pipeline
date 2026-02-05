"""
Migration script to add new property fields to the database

Adds: bathrooms, added_on, reduced_on, size, tenure, council_tax_band
"""
import asyncio
import asyncpg
from db.config import DB_CONFIG


async def migrate():
    """Add new columns to properties table"""

    conn = await asyncpg.connect(**DB_CONFIG)

    print("Starting migration: Adding new property fields...")

    try:
        # Add bathrooms column
        print("Adding bathrooms column...")
        await conn.execute("""
            ALTER TABLE properties
            ADD COLUMN IF NOT EXISTS bathrooms VARCHAR(20)
        """)

        # Add added_on column
        print("Adding added_on column...")
        await conn.execute("""
            ALTER TABLE properties
            ADD COLUMN IF NOT EXISTS added_on VARCHAR(20)
        """)

        # Add reduced_on column
        print("Adding reduced_on column...")
        await conn.execute("""
            ALTER TABLE properties
            ADD COLUMN IF NOT EXISTS reduced_on VARCHAR(20)
        """)

        # Add size column
        print("Adding size column...")
        await conn.execute("""
            ALTER TABLE properties
            ADD COLUMN IF NOT EXISTS size VARCHAR(50)
        """)

        # Add tenure column
        print("Adding tenure column...")
        await conn.execute("""
            ALTER TABLE properties
            ADD COLUMN IF NOT EXISTS tenure VARCHAR(50)
        """)

        # Add council_tax_band column
        print("Adding council_tax_band column...")
        await conn.execute("""
            ALTER TABLE properties
            ADD COLUMN IF NOT EXISTS council_tax_band VARCHAR(10)
        """)

        print("\nMigration completed successfully!")
        print("\nNew columns added:")
        print("  - bathrooms (VARCHAR(20))")
        print("  - added_on (VARCHAR(20))")
        print("  - reduced_on (VARCHAR(20))")
        print("  - size (VARCHAR(50))")
        print("  - tenure (VARCHAR(50))")
        print("  - council_tax_band (VARCHAR(10))")

    except Exception as e:
        print(f"\nMigration failed: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())
