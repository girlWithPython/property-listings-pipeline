"""
Test the new deduplication logic

This test verifies that identical snapshots are not saved (preventing disk waste)
"""
import asyncio
from db.database import DatabaseConnector
from db.config import DB_CONFIG

async def test_deduplication():
    print("=" * 80)
    print("TEST: Deduplication Logic")
    print("=" * 80)

    db = DatabaseConnector()
    await db.connect(**DB_CONFIG)

    try:
        # Test data - same property scraped twice with identical data
        property_data_1 = {
            "property_id": "TEST123456",
            "url": "https://test.com/properties/TEST123456",
            "price": 350000,
            "bedrooms": 3,
            "description": "Test property",
            "full_address": "Test Street, Test Town",
            "address_parts": {
                "line1": "Test Street",
                "county": "Test County",
                "postcode": None
            },
            "coordinates": {
                "latitude": 51.5,
                "longitude": -0.1
            },
            "price_qualifier": None,
            "property_type": "Detached",
            "status": "For Sale",
            "tenure": "Freehold",
            "bathrooms": 2,
            "added_on": None,
            "reduced_on": None,
            "size": 1000,
            "council_tax_band": "D"
        }

        # Scenario 1: First insertion (should succeed)
        print("\n[TEST 1] First insertion of property TEST123456")
        success, status = await db.insert_property(property_data_1, "Test Town")
        print(f"  Result: success={success}, status={status}")
        assert status == 'inserted', f"Expected 'inserted', got '{status}'"
        print("  [PASS] First insertion succeeded")

        # Scenario 2: Second insertion with IDENTICAL data (should skip)
        print("\n[TEST 2] Second insertion with identical data (should SKIP)")
        property_data_2 = property_data_1.copy()  # Exact same data
        success, status = await db.insert_property(property_data_2, "Test Town")
        print(f"  Result: success={success}, status={status}")
        assert status == 'skipped', f"Expected 'skipped', got '{status}'"
        print("  [PASS] Duplicate skipped correctly")

        # Scenario 3: Third insertion with CHANGED price (should insert)
        print("\n[TEST 3] Third insertion with changed price (should INSERT)")
        property_data_3 = property_data_1.copy()
        property_data_3["price"] = 340000  # Price reduced
        success, status = await db.insert_property(property_data_3, "Test Town")
        print(f"  Result: success={success}, status={status}")
        assert status == 'inserted', f"Expected 'inserted', got '{status}'"
        print("  [PASS] Price change inserted correctly")

        # Scenario 4: Fourth insertion with SAME data as scenario 3 (should skip)
        print("\n[TEST 4] Fourth insertion with same price as scenario 3 (should SKIP)")
        property_data_4 = property_data_3.copy()  # Same as reduced price
        success, status = await db.insert_property(property_data_4, "Test Town")
        print(f"  Result: success={success}, status={status}")
        assert status == 'skipped', f"Expected 'skipped', got '{status}'"
        print("  [PASS] Duplicate with same price skipped")

        # Verify total snapshots
        print("\n" + "=" * 80)
        print("VERIFICATION")
        print("=" * 80)

        async with db.pool.acquire() as conn:
            snapshots = await conn.fetch("""
                SELECT price, created_at
                FROM properties
                WHERE property_id = 'TEST123456'
                ORDER BY created_at ASC
            """)

        print(f"\nTotal snapshots for TEST123456: {len(snapshots)}")
        for idx, snap in enumerate(snapshots, 1):
            print(f"  Snapshot {idx}: price=£{snap['price']:,}, created={snap['created_at']}")

        assert len(snapshots) == 2, f"Expected 2 snapshots, got {len(snapshots)}"
        print("\n[PASS] Correct number of snapshots (2)")

        # Cleanup
        print("\n" + "=" * 80)
        print("CLEANUP")
        print("=" * 80)
        async with db.pool.acquire() as conn:
            await conn.execute("DELETE FROM properties WHERE property_id = 'TEST123456'")
        print("Test data deleted")

        print("\n" + "=" * 80)
        print("ALL TESTS PASSED!")
        print("=" * 80)
        print("\nDeduplication logic working correctly:")
        print("  - Identical snapshots are SKIPPED (saves disk space)")
        print("  - Changed snapshots are INSERTED (tracks history)")
        print("  - Oldest snapshot with same data is preserved")

    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(test_deduplication())
