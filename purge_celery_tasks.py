"""
Purge all pending Celery tasks
"""
from workers.celery_app import app


def purge_all_tasks():
    """Remove all pending tasks from all queues"""

    # Purge all tasks
    result = app.control.purge()

    if result:
        total_purged = sum(result.values())
        print(f"\nPurged {total_purged} tasks from queues")
        print("\nBreakdown by worker:")
        for worker, count in result.items():
            print(f"  {worker}: {count} tasks")
    else:
        print("\nNo tasks to purge or no workers available")

    # Also clear the broker (Redis)
    print("\nClearing Redis queues...")
    from redis import Redis
    import os

    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    redis_client = Redis.from_url(redis_url)

    # Delete all Celery queue keys
    queues = ['celery', 'scraper', 'geocoding', 'email']
    for queue in queues:
        deleted = redis_client.delete(queue)
        if deleted:
            print(f"  Cleared queue: {queue}")

    print("\n✓ All tasks purged successfully")


if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("CELERY TASK PURGE")
    print("=" * 60)
    print("\nThis will remove ALL pending tasks from all queues.")

    response = input("\nAre you sure? (yes/no): ").strip().lower()

    if response in ['yes', 'y']:
        purge_all_tasks()
    else:
        print("\nPurge cancelled")
        sys.exit(0)
