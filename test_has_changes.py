"""
Direct test of the has_changes() function
Tests the new deduplication logic without full property insertion
"""
import asyncio
import asyncpg
from db.config import DB_CONFIG
from db.database import DatabaseConnector

async def test_has_changes():
    print("=" * 80)
    print("TEST: has_changes() Deduplication Logic")
    print("=" * 80)

    conn = await asyncpg.connect(**DB_CONFIG)
    db = DatabaseConnector()
    db.pool = await asyncpg.create_pool(**DB_CONFIG)

    try:
        # Create a test property with 2 snapshots
        test_property_id = "TEST_HAS_CHANGES_999"

        # Clean up any existing test data
        await conn.execute("DELETE FROM properties WHERE property_id = $1", test_property_id)

        print("\n[SETUP] Creating test property with 2 snapshots...")

        # Snapshot 1: Original price £300,000
        await conn.execute("""
            INSERT INTO properties (
                id, property_id, town_id, url, price, status_id, offer_type_id, reduced_on, created_at
            ) VALUES ($1, $2, 1, 'https://test.com/test', 300000, 1, NULL, NULL, NOW() - INTERVAL '2 days')
        """, "00000000-0000-0000-0000-000000000001", test_property_id)

        # Snapshot 2: Price reduced to £290,000
        await conn.execute("""
            INSERT INTO properties (
                id, property_id, town_id, url, price, status_id, offer_type_id, reduced_on, created_at
            ) VALUES ($1, $2, 1, 'https://test.com/test', 290000, 1, NULL, '2026-01-01', NOW() - INTERVAL '1 day')
        """, "00000000-0000-0000-0000-000000000002", test_property_id)

        print("  [OK] Created 2 snapshots (£300k and £290k)")

        # Test 1: Check if identical data to snapshot 1 is detected
        print("\n[TEST 1] New data identical to snapshot 1 (£300k)")
        new_data_1 = {
            "price": 300000,
            "status_id": 1,
            "offer_type_id": None,
            "reduced_on": None
        }
        has_changes_1 = await db.has_changes(test_property_id, new_data_1)
        print(f"  Result: has_changes = {has_changes_1}")
        assert has_changes_1 == False, "Should detect identical snapshot and return False"
        print("  [PASS] Correctly detected duplicate (older snapshot)")

        # Test 2: Check if identical data to snapshot 2 is detected
        print("\n[TEST 2] New data identical to snapshot 2 (£290k)")
        new_data_2 = {
            "price": 290000,
            "status_id": 1,
            "offer_type_id": None,
            "reduced_on": "2026-01-01"
        }
        has_changes_2 = await db.has_changes(test_property_id, new_data_2)
        print(f"  Result: has_changes = {has_changes_2}")
        assert has_changes_2 == False, "Should detect identical snapshot and return False"
        print("  [PASS] Correctly detected duplicate (recent snapshot)")

        # Test 3: Check if different price is detected as change
        print("\n[TEST 3] New data with different price (£280k)")
        new_data_3 = {
            "price": 280000,  # New price
            "status_id": 1,
            "offer_type_id": None,
            "reduced_on": "2026-01-15"
        }
        has_changes_3 = await db.has_changes(test_property_id, new_data_3)
        print(f"  Result: has_changes = {has_changes_3}")
        assert has_changes_3 == True, "Should detect price change and return True"
        print("  [PASS] Correctly detected price change")

        # Test 4: Check if different status is detected as change
        print("\n[TEST 4] New data with different status (SOLD STC)")
        new_data_4 = {
            "price": 290000,  # Same as snapshot 2
            "status_id": 2,   # Different status
            "offer_type_id": None,
            "reduced_on": "2026-01-01"
        }
        has_changes_4 = await db.has_changes(test_property_id, new_data_4)
        print(f"  Result: has_changes = {has_changes_4}")
        assert has_changes_4 == True, "Should detect status change and return True"
        print("  [PASS] Correctly detected status change")

        # Cleanup
        print("\n" + "=" * 80)
        print("CLEANUP")
        print("=" * 80)
        await conn.execute("DELETE FROM properties WHERE property_id = $1", test_property_id)
        print("Test data deleted")

        print("\n" + "=" * 80)
        print("ALL TESTS PASSED!")
        print("=" * 80)
        print("\nDeduplication logic verified:")
        print("  - Detects identical snapshots (any in history)")
        print("  - Returns False when duplicate found (saves disk space)")
        print("  - Returns True when data changed (inserts new snapshot)")

    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        await conn.close()
        await db.pool.close()

if __name__ == "__main__":
    asyncio.run(test_has_changes())
