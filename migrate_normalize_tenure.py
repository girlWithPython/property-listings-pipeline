"""
Migration script to normalize tenure field

This migration:
1. Creates tenure_types table
2. Populates it with existing tenure values
3. Adds tenure_id column to properties
4. Links existing properties to tenure_types
5. Removes old tenure column

Safe to run multiple times (idempotent)
"""
import asyncio
import asyncpg
from db.config import DB_CONFIG


async def migrate():
    """Normalize tenure field"""
    conn = await asyncpg.connect(**DB_CONFIG)

    print("=" * 80)
    print("TENURE NORMALIZATION MIGRATION")
    print("=" * 80)

    try:
        # Step 1: Create tenure_types table
        print("\nStep 1: Creating tenure_types table...")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS tenure_types (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) NOT NULL UNIQUE
            );
        """)
        print("  OK tenure_types table created")

        # Step 2: Check if old tenure column exists
        print("\nStep 2: Checking for existing tenure column...")

        tenure_col_exists = await conn.fetchval("""
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_name = 'properties'
            AND column_name = 'tenure'
        """)

        if not tenure_col_exists:
            print("  ! tenure column doesn't exist - migration may have already run")
            print("  Continuing anyway to ensure tenure_types is populated...")

        # Step 3: Extract distinct tenure values and populate tenure_types
        print("\nStep 3: Populating tenure_types table...")

        if tenure_col_exists:
            # Get distinct non-null tenure values
            distinct_tenures = await conn.fetch("""
                SELECT DISTINCT tenure
                FROM properties
                WHERE tenure IS NOT NULL
                ORDER BY tenure
            """)

            if distinct_tenures:
                print(f"  Found {len(distinct_tenures)} distinct tenure values:")
                for row in distinct_tenures:
                    print(f"    - {row['tenure']}")

                # Insert into tenure_types (ON CONFLICT DO NOTHING makes it idempotent)
                for row in distinct_tenures:
                    await conn.execute("""
                        INSERT INTO tenure_types (name)
                        VALUES ($1)
                        ON CONFLICT (name) DO NOTHING
                    """, row['tenure'])

                print(f"  OK Inserted {len(distinct_tenures)} tenure types")
            else:
                print("  ! No tenure values found in properties table")
                # Insert common UK tenure types anyway
                print("  Inserting standard UK tenure types...")
                await conn.execute("""
                    INSERT INTO tenure_types (name)
                    VALUES ('Freehold'), ('Leasehold')
                    ON CONFLICT (name) DO NOTHING
                """)
                print("  OK Inserted standard tenure types")
        else:
            # Ensure standard tenure types exist
            print("  Ensuring standard tenure types exist...")
            await conn.execute("""
                INSERT INTO tenure_types (name)
                VALUES ('Freehold'), ('Leasehold')
                ON CONFLICT (name) DO NOTHING
            """)
            print("  OK Standard tenure types ready")

        # Step 4: Add tenure_id column to properties
        print("\nStep 4: Adding tenure_id column to properties...")

        tenure_id_exists = await conn.fetchval("""
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_name = 'properties'
            AND column_name = 'tenure_id'
        """)

        if not tenure_id_exists:
            await conn.execute("""
                ALTER TABLE properties
                ADD COLUMN tenure_id INTEGER REFERENCES tenure_types(id)
            """)
            print("  OK tenure_id column added")
        else:
            print("  ! tenure_id column already exists")

        # Step 5: Link existing properties to tenure_types
        if tenure_col_exists:
            print("\nStep 5: Linking existing properties to tenure_types...")

            # Update properties to use tenure_id
            updated = await conn.execute("""
                UPDATE properties p
                SET tenure_id = t.id
                FROM tenure_types t
                WHERE p.tenure = t.name
                AND p.tenure_id IS NULL
            """)

            # Extract count from result string like "UPDATE 20"
            update_count = int(updated.split()[-1]) if updated.split()[-1].isdigit() else 0
            print(f"  OK Linked {update_count} properties to tenure_types")

            # Check for unmapped properties
            unmapped = await conn.fetchval("""
                SELECT COUNT(*)
                FROM properties
                WHERE tenure IS NOT NULL
                AND tenure_id IS NULL
            """)

            if unmapped > 0:
                print(f"  ! Warning: {unmapped} properties have tenure but no tenure_id")
                print("    These may have tenure values not in tenure_types table")
        else:
            print("\nStep 5: Skipped (no old tenure column to migrate)")

        # Step 6: Drop old tenure column
        if tenure_col_exists:
            print("\nStep 6: Dropping old tenure column...")

            # Ask for confirmation
            print("\n" + "=" * 80)
            print("WARNING  IMPORTANT: About to drop the old 'tenure' column")
            print("All data has been migrated to tenure_id")
            print("=" * 80)
            response = input("\nProceed with dropping 'tenure' column? (yes/no): ").strip().lower()

            if response in ['yes', 'y']:
                await conn.execute("""
                    ALTER TABLE properties
                    DROP COLUMN tenure
                """)
                print("  OK Old tenure column dropped")
            else:
                print("  - Skipped dropping tenure column (keeping for now)")
                print("    You can manually drop it later with:")
                print("    ALTER TABLE properties DROP COLUMN tenure;")
        else:
            print("\nStep 6: Skipped (tenure column already removed)")

        # Step 7: Show summary
        print("\n" + "=" * 80)
        print("MIGRATION SUMMARY")
        print("=" * 80)

        # Count tenure types
        tenure_type_count = await conn.fetchval("SELECT COUNT(*) FROM tenure_types")
        print(f"\nTenure types in database: {tenure_type_count}")

        # Show all tenure types
        tenure_types = await conn.fetch("SELECT id, name FROM tenure_types ORDER BY id")
        for tt in tenure_types:
            count = await conn.fetchval("""
                SELECT COUNT(*) FROM properties WHERE tenure_id = $1
            """, tt['id'])
            print(f"  [{tt['id']}] {tt['name']}: {count} properties")

        # Count properties with no tenure
        no_tenure = await conn.fetchval("""
            SELECT COUNT(*) FROM properties WHERE tenure_id IS NULL
        """)
        print(f"  [NULL] No tenure: {no_tenure} properties")

        print("\n" + "=" * 80)
        print("OK MIGRATION COMPLETED SUCCESSFULLY")
        print("=" * 80)

    except Exception as e:
        print(f"\nERROR Migration failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())
