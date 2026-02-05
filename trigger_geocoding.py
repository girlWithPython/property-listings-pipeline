"""
Trigger geocoding tasks manually

Usage:
    # Geocode all missing postcodes
    python trigger_geocoding.py

    # Geocode a specific postcode
    python trigger_geocoding.py --postcode "KT19 9PR"

    # Check task status
    python trigger_geocoding.py --status <task_id>
"""
import argparse
import sys
from workers.geocoding import reverse_geocode_missing_postcodes, reverse_geocode_single
from celery.result import AsyncResult
from workers.celery_app import app


def main():
    parser = argparse.ArgumentParser(description='Trigger geocoding tasks')
    parser.add_argument(
        '--postcode',
        type=str,
        help='Geocode a specific postcode'
    )
    parser.add_argument(
        '--status',
        type=str,
        help='Check status of a task by ID'
    )

    args = parser.parse_args()

    if args.status:
        # Check task status
        result = AsyncResult(args.status, app=app)
        print(f"\nTask ID: {args.status}")
        print(f"Status: {result.state}")

        if result.ready():
            if result.successful():
                print(f"Result: {result.result}")
            else:
                print(f"Error: {result.info}")
        else:
            print("Task is still processing...")

    elif args.postcode:
        # Geocode specific coordinates (requires lat,lon format)
        print(f"\nNote: Use --lat and --lon instead of --postcode for single coordinate")
        print(f"For batch processing, use default (no args)")
        return

    else:
        # Geocode all properties with missing data
        print("\nTriggering reverse geocoding for properties with missing data...")
        print("(This includes properties with partial/null postcodes OR null county)")
        task = reverse_geocode_missing_postcodes.delay()
        print(f"\nTask ID: {task.id}")
        print(f"Status: {task.state}")
        print(f"\nTo check status, run:")
        print(f"  python trigger_geocoding.py --status {task.id}")


if __name__ == '__main__':
    main()
