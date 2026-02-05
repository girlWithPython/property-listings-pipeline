"""
Trigger the scraper worker task

This runs the scraper as a background Celery task, which automatically:
1. Scrapes all enabled search URLs from scraper/search_urls.py
2. Saves properties to the database
3. Queues image downloads
4. Triggers reverse geocoding for new properties

Usage:
    # Run the scraper
    python trigger_scraper.py

    # Check task status
    python trigger_scraper.py --status <task_id>
"""
import argparse
from workers.scraper_tasks import run_scraper
from celery.result import AsyncResult
from workers.celery_app import app


def main():
    parser = argparse.ArgumentParser(description='Trigger scraper worker task')
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

    else:
        # Trigger scraper
        print("\nTriggering Rightmove scraper...")
        print("=" * 60)
        print("The scraper will:")
        print("  1. Scrape all enabled search URLs")
        print("  2. Save properties to database")
        print("  3. Queue image downloads")
        print("  4. Automatically run reverse geocoding")
        print("=" * 60)

        task = run_scraper.delay()
        print(f"\nTask ID: {task.id}")
        print(f"Status: {task.state}")
        print(f"\nTo check status, run:")
        print(f"  python trigger_scraper.py --status {task.id}")

        print("\nMonitor worker logs:")
        print("  docker logs rightmove_worker --follow")


if __name__ == '__main__':
    main()
