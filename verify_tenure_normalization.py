"""
Verify tenure normalization is working correctly
"""
import asyncio
import asyncpg
from db.config import DB_CONFIG


async def verify():
    conn = await asyncpg.connect(**DB_CONFIG)

    print("=" * 80)
    print("TENURE NORMALIZATION VERIFICATION")
    print("=" * 80)

    # Check tenure_types table
    print("\n1. Tenure Types Table:")
    tenure_types = await conn.fetch("""
        SELECT id, name
        FROM tenure_types
        ORDER BY id
    """)

    if tenure_types:
        print(f"\n   Found {len(tenure_types)} tenure type(s):")
        for tt in tenure_types:
            print(f"   [{tt['id']}] {tt['name']}")
    else:
        print("   ! No tenure types found")

    # Check properties table structure
    print("\n2. Properties Table Structure:")
    columns = await conn.fetch("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'properties'
        AND column_name IN ('tenure', 'tenure_id')
        ORDER BY column_name
    """)

    for col in columns:
        print(f"   - {col['column_name']}: {col['data_type']}")

    # Check if old tenure column still exists
    old_column_exists = await conn.fetchval("""
        SELECT COUNT(*)
        FROM information_schema.columns
        WHERE table_name = 'properties'
        AND column_name = 'tenure'
    """)

    if old_column_exists:
        print("   WARNING: Old 'tenure' column still exists!")
    else:
        print("   OK: Old 'tenure' column has been removed")

    # Count properties by tenure
    print("\n3. Properties by Tenure:")
    tenure_counts = await conn.fetch("""
        SELECT
            tt.id,
            tt.name,
            COUNT(p.id) as property_count
        FROM tenure_types tt
        LEFT JOIN properties p ON p.tenure_id = tt.id
        GROUP BY tt.id, tt.name
        ORDER BY tt.id
    """)

    for tc in tenure_counts:
        print(f"   [{tc['id']}] {tc['name']}: {tc['property_count']} properties")

    # Count properties with no tenure
    no_tenure = await conn.fetchval("""
        SELECT COUNT(*)
        FROM properties
        WHERE tenure_id IS NULL
    """)
    print(f"   [NULL] No tenure: {no_tenure} properties")

    # Show sample properties
    print("\n4. Sample Properties:")
    sample = await conn.fetch("""
        SELECT DISTINCT ON (p.property_id)
            p.property_id,
            p.full_address,
            tt.name as tenure,
            p.price
        FROM properties p
        LEFT JOIN tenure_types tt ON p.tenure_id = tt.id
        ORDER BY p.property_id, p.created_at DESC
        LIMIT 5
    """)

    for prop in sample:
        tenure = prop['tenure'] if prop['tenure'] else 'None'
        print(f"   {prop['property_id']}: {tenure} - {prop['full_address'][:50]}")

    print("\n" + "=" * 80)
    print("VERIFICATION COMPLETE")
    print("=" * 80)

    await conn.close()


if __name__ == "__main__":
    asyncio.run(verify())
