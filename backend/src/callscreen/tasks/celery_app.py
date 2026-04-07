"""Celery application configuration."""

from celery import Celery

from callscreen.config import get_settings

settings = get_settings()

app = Celery(
    "callscreen",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "sync-blocklists": {
            "task": "callscreen.tasks.scheduled.sync_blocklists",
            "schedule": 86400.0,  # daily
        },
        "send-daily-digests": {
            "task": "callscreen.tasks.scheduled.send_daily_digests",
            "schedule": 86400.0,  # daily
        },
    },
)

app.autodiscover_tasks(["callscreen.tasks"])
