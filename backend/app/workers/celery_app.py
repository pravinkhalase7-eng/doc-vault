from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "docvault",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    beat_schedule={
        "expiry-scan": {"task": "app.workers.tasks.scan_expiries", "schedule": crontab(hour=2, minute=15)},
        "daily-briefing": {"task": "app.workers.tasks.daily_briefing", "schedule": crontab(hour=6, minute=0)},
        "weekly-report": {"task": "app.workers.tasks.weekly_report", "schedule": crontab(hour=7, minute=0, day_of_week=1)},
        "purge-trash": {"task": "app.workers.tasks.purge_trash", "schedule": crontab(hour=3, minute=30)},
        "due-reminder-calls": {"task": "app.workers.tasks.fire_due_reminder_calls", "schedule": 60.0},
        "shared-inbox-poll": {"task": "app.workers.tasks.poll_shared_inbox", "schedule": 60.0},
    },
)
