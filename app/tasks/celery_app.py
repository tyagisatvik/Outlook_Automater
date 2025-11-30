"""Celery application configuration"""
from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "email_intelligence",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.email_tasks", "app.tasks.subscription_renewal"]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes hard limit
    task_soft_time_limit=240,  # 4 minutes soft limit
    worker_prefetch_multiplier=1,  # Fetch one task at a time
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks
    result_expires=3600,  # Results expire after 1 hour
    task_acks_late=True,  # Acknowledge task after completion
    task_reject_on_worker_lost=True,
)

# Periodic tasks schedule (Celery Beat)
celery_app.conf.beat_schedule = {
    "renew-webhook-subscriptions": {
        "task": "app.tasks.subscription_renewal.renew_expiring_subscriptions",
        "schedule": crontab(minute="0"),  # Run every hour
    },
}
