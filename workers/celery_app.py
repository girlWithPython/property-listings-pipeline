"""
Celery application configuration
"""
from celery import Celery
import os

# Redis URL for broker and backend
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Create Celery app
app = Celery(
    'rightmove_workers',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        'workers.geocoding',
        'workers.scraper_tasks',
        'workers.email_tasks',
        'workers.image_tasks',
    ]
)

# Celery configuration
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,

    # Task routing
    task_routes={
        'workers.geocoding.*': {'queue': 'geocoding'},
        'workers.scraper_tasks.*': {'queue': 'scraper'},
        'workers.email_tasks.*': {'queue': 'email'},
        'workers.image_tasks.*': {'queue': 'scraper'},
    },

    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,

    # Retry settings
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,

    # Result backend settings
    result_expires=3600,  # 1 hour
)

if __name__ == '__main__':
    app.start()
