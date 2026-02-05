"""
Migration script to change size column from VARCHAR to INTEGER

This will:
1. Drop the existing size column (if it has VARCHAR data)
2. Add a new size column as INTEGER
"""
import asyncio
import asyncpg
from db.config import DB_CONFIG


async def migrate():
    """Change size column to INTEGER"""
    conn = await asyncpg.connect(**DB_CONFIG)
    print("Starting migration: Changing size column to INTEGER...")

    try:
        # Check if size column exists
        result = await conn.fetchval("""
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_name='properties' AND column_name='size'
        """)

        if result > 0:
            print("\nDropping existing size column...")
            await conn.execute("""
                ALTER TABLE properties
                DROP COLUMN size
            """)

        print("Adding size column as INTEGER...")
        await conn.execute("""
            ALTER TABLE properties
            ADD COLUMN size INTEGER
        """)

        print("\nMigration completed successfully!")
        print("\nColumn updated:")
        print("  - size: VARCHAR(50) -> INTEGER")
        print("\nNote: Existing size data has been cleared. Re-run scraper to populate.")

    except Exception as e:
        print(f"\nMigration failed: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())
