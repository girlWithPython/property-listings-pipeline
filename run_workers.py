"""
Start Celery workers for different queues

Usage:
    # Start all workers (default)
    python run_workers.py

    # Start specific worker
    python run_workers.py --queue geocoding
    python run_workers.py --queue scraper
    python run_workers.py --queue email

    # Start with more workers (concurrency)
    python run_workers.py --concurrency 4
"""
import sys
import argparse
from workers.celery_app import app


def main():
    parser = argparse.ArgumentParser(description='Run Celery workers')
    parser.add_argument(
        '--queue',
        choices=['geocoding', 'scraper', 'email', 'all'],
        default='all',
        help='Which queue to process (default: all)'
    )
    parser.add_argument(
        '--concurrency',
        type=int,
        default=2,
        help='Number of worker processes (default: 2)'
    )
    parser.add_argument(
        '--loglevel',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )

    args = parser.parse_args()

    # Build worker arguments
    worker_args = [
        'worker',
        f'--loglevel={args.loglevel}',
        f'--concurrency={args.concurrency}',
    ]

    # Add queue specification
    if args.queue == 'all':
        worker_args.append('--queues=geocoding,scraper,email')
    else:
        worker_args.append(f'--queues={args.queue}')

    # Add worker name
    worker_args.append(f'--hostname={args.queue}@%h')

    print("=" * 80)
    print(f"Starting Celery Worker")
    print("=" * 80)
    print(f"Queue(s): {args.queue}")
    print(f"Concurrency: {args.concurrency}")
    print(f"Log level: {args.loglevel}")
    print("=" * 80)
    print("\nPress Ctrl+C to stop\n")

    # Start worker
    app.worker_main(argv=worker_args)


if __name__ == '__main__':
    main()
