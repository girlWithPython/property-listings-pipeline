"""Show final database state after reverse geocoding"""
import asyncio
from db.database import DatabaseConnector
from db.config import DB_CONFIG


async def main():
    db = DatabaseConnector()
    await db.connect(**DB_CONFIG)

    print("=" * 80)
    print("FINAL DATABASE STATE - ALL PROPERTIES")
    print("=" * 80)

    async with db.pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT DISTINCT ON (property_id)
                property_id, full_address, postcode, county, locality,
                latitude, longitude, price
            FROM properties
            ORDER BY property_id, created_at DESC
        """)

        for r in rows:
            print(f"\nProperty ID: {r['property_id']}")
            print(f"  Address: {r['full_address']}")
            print(f"  Postcode: {r['postcode']}")
            print(f"  County: {r['county']}")
            print(f"  Locality: {r['locality']}")
            print(f"  Coordinates: ({r['latitude']}, {r['longitude']})")
            if r['price']:
                print(f"  Price: £{r['price']:,}")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    async with db.pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(DISTINCT property_id) FROM properties")
        with_postcode = await conn.fetchval("""
            SELECT COUNT(DISTINCT property_id)
            FROM (
                SELECT DISTINCT ON (property_id) property_id, postcode
                FROM properties
                ORDER BY property_id, created_at DESC
            ) latest
            WHERE postcode IS NOT NULL
        """)
        with_county = await conn.fetchval("""
            SELECT COUNT(DISTINCT property_id)
            FROM (
                SELECT DISTINCT ON (property_id) property_id, county
                FROM properties
                ORDER BY property_id, created_at DESC
            ) latest
            WHERE county IS NOT NULL
        """)

        print(f"Total unique properties: {total}")
        print(f"With full postcodes: {with_postcode}")
        print(f"With county info: {with_county}")
        print("=" * 80)

    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
