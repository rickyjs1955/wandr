"""
Celery application configuration.

Handles:
- Celery app initialization
- Task auto-discovery
- Result backend configuration
- Queue routing
- Worker configuration
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

# Create Celery application
celery_app = Celery(
    "spatial_intel",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution settings
    task_track_started=True,
    task_time_limit=3600,  # 1 hour hard limit
    task_soft_time_limit=3300,  # 55 minutes soft limit
    task_acks_late=True,  # Acknowledge after task completion
    task_reject_on_worker_lost=True,

    # Result backend settings
    result_expires=86400,  # Results expire after 24 hours
    result_extended=True,  # Store additional metadata

    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time (for video processing)
    worker_max_tasks_per_child=10,  # Restart worker after 10 tasks (memory management)
    worker_disable_rate_limits=False,

    # Task routing
    task_routes={
        "app.tasks.video_tasks.*": {"queue": "video_processing"},
        "app.tasks.analysis_tasks.*": {"queue": "cv_analysis"},
        "app.tasks.maintenance_tasks.*": {"queue": "maintenance"},
    },

    # Task priority
    task_default_priority=5,

    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,

    # Redis connection pool
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,

    # Beat schedule (for periodic tasks - Phase 2.7)
    beat_schedule={
        # Example: Clean up old processing jobs
        "cleanup-old-jobs": {
            "task": "app.tasks.maintenance_tasks.cleanup_old_jobs",
            "schedule": crontab(hour=2, minute=0),  # 2 AM daily
        },
        # Example: Check for stuck jobs
        "check-stuck-jobs": {
            "task": "app.tasks.maintenance_tasks.check_stuck_jobs",
            "schedule": crontab(minute="*/15"),  # Every 15 minutes
        },
    },
)

# Auto-discover tasks from all registered apps
celery_app.autodiscover_tasks(
    [
        "app.tasks.video_tasks",
        "app.tasks.analysis_tasks",
        "app.tasks.maintenance_tasks",
    ],
    force=True,
)


# Task base configuration
@celery_app.task(bind=True, name="app.core.celery_app.debug_task")
def debug_task(self):
    """Debug task for testing Celery setup."""
    print(f"Request: {self.request!r}")
    return {"status": "success", "message": "Celery is working!"}


# Signals for task lifecycle events
from celery.signals import (
    task_prerun,
    task_postrun,
    task_failure,
    task_success,
    task_retry,
)
import logging

logger = logging.getLogger(__name__)


@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra):
    """Log when task starts."""
    logger.info(f"Task {task.name} [{task_id}] starting")


@task_postrun.connect
def task_postrun_handler(
    sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **extra
):
    """Log when task completes."""
    logger.info(f"Task {task.name} [{task_id}] completed with state: {state}")


@task_failure.connect
def task_failure_handler(
    sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, einfo=None, **extra
):
    """Log when task fails."""
    logger.error(
        f"Task {sender.name} [{task_id}] failed: {exception}",
        exc_info=einfo,
    )


@task_success.connect
def task_success_handler(sender=None, result=None, **extra):
    """Log when task succeeds."""
    logger.info(f"Task {sender.name} succeeded with result: {result}")


@task_retry.connect
def task_retry_handler(
    sender=None, task_id=None, reason=None, einfo=None, **extra
):
    """Log when task is retried."""
    logger.warning(f"Task {sender.name} [{task_id}] retrying: {reason}")
