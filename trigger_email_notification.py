"""
Trigger email notification tasks manually

Usage:
    # Send notification about snapshots in last 60 minutes
    python trigger_email_notification.py

    # Send notification about snapshots in last 24 hours
    python trigger_email_notification.py --minutes 1440

    # Send price alert
    python trigger_email_notification.py --price-alert 171541316 200000 195000

    # Check task status
    python trigger_email_notification.py --status <task_id>
"""
import argparse
from workers.email_tasks import send_new_snapshots_notification, send_price_alert
from celery.result import AsyncResult
from workers.celery_app import app


def main():
    parser = argparse.ArgumentParser(description='Trigger email notification tasks')
    parser.add_argument(
        '--minutes',
        type=int,
        default=60,
        help='Send notification for snapshots added in the last N minutes (default: 60)'
    )
    parser.add_argument(
        '--price-alert',
        nargs=3,
        metavar=('PROPERTY_ID', 'OLD_PRICE', 'NEW_PRICE'),
        help='Send price alert for a property'
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

    elif args.price_alert:
        # Send price alert
        property_id, old_price, new_price = args.price_alert
        print(f"\nTriggering price alert for property {property_id}...")
        print(f"Price change: £{old_price} → £{new_price}")

        task = send_price_alert.delay(property_id, int(old_price), int(new_price))
        print(f"\nTask ID: {task.id}")
        print(f"Status: {task.state}")
        print(f"\nTo check status, run:")
        print(f"  python trigger_email_notification.py --status {task.id}")

    else:
        # Send new snapshots notification
        print(f"\nTriggering email notification for snapshots in the last {args.minutes} minutes...")

        task = send_new_snapshots_notification.delay(args.minutes)
        print(f"\nTask ID: {task.id}")
        print(f"Status: {task.state}")
        print(f"\nTo check status, run:")
        print(f"  python trigger_email_notification.py --status {task.id}")


if __name__ == '__main__':
    main()
