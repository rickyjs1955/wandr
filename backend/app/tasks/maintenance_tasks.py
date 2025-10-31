"""
Maintenance tasks.

Celery periodic tasks for:
- Cleanup old processing jobs
- Check for stuck jobs
- System health monitoring
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

from celery import Task
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models import ProcessingJob, Video

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Base task with database session management."""

    _db: Session = None

    @property
    def db(self) -> Session:
        """Get database session."""
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        """Close database session after task completion."""
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="app.tasks.maintenance_tasks.cleanup_old_jobs",
)
def cleanup_old_jobs(self, days_to_keep: int = 30) -> Dict[str, Any]:
    """
    Clean up old completed/failed processing jobs.

    Runs daily at 2 AM (configured in beat_schedule).

    Args:
        days_to_keep: Keep jobs from last N days (default 30)

    Returns:
        Dict with cleanup statistics
    """
    logger.info(f"Starting cleanup of jobs older than {days_to_keep} days")

    cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

    try:
        # Find old completed/failed jobs
        old_jobs = (
            self.db.query(ProcessingJob)
            .filter(
                and_(
                    ProcessingJob.completed_at < cutoff_date,
                    ProcessingJob.status.in_(["completed", "failed"]),
                )
            )
            .all()
        )

        deleted_count = len(old_jobs)

        # Delete old jobs
        for job in old_jobs:
            self.db.delete(job)

        self.db.commit()

        logger.info(f"✅ Cleaned up {deleted_count} old processing jobs")

        return {
            "status": "completed",
            "deleted_count": deleted_count,
            "cutoff_date": cutoff_date.isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")
        self.db.rollback()
        raise


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="app.tasks.maintenance_tasks.check_stuck_jobs",
)
def check_stuck_jobs(
    self,
    stuck_threshold_minutes: int = 120,
) -> Dict[str, Any]:
    """
    Check for stuck jobs and mark them as failed.

    A job is considered stuck if:
    - Status is 'pending' or 'running'
    - Started more than stuck_threshold_minutes ago
    - No progress updates

    Runs every 15 minutes (configured in beat_schedule).

    Args:
        stuck_threshold_minutes: Consider job stuck after N minutes (default 120)

    Returns:
        Dict with stuck job statistics
    """
    logger.info(f"Checking for stuck jobs (threshold: {stuck_threshold_minutes} minutes)")

    cutoff_time = datetime.utcnow() - timedelta(minutes=stuck_threshold_minutes)

    try:
        # Find potentially stuck jobs
        stuck_jobs = (
            self.db.query(ProcessingJob)
            .filter(
                and_(
                    ProcessingJob.status.in_(["pending", "running"]),
                    or_(
                        # Pending jobs queued too long ago
                        and_(
                            ProcessingJob.status == "pending",
                            ProcessingJob.queued_at < cutoff_time,
                        ),
                        # Running jobs started too long ago
                        and_(
                            ProcessingJob.status == "running",
                            ProcessingJob.started_at < cutoff_time,
                        ),
                    ),
                )
            )
            .all()
        )

        stuck_count = len(stuck_jobs)
        stuck_job_ids: List[str] = []

        # Mark stuck jobs as failed
        for job in stuck_jobs:
            logger.warning(
                f"Marking stuck job as failed: job_id={job.id}, "
                f"status={job.status}, queued_at={job.queued_at}, "
                f"started_at={job.started_at}"
            )

            job.status = "failed"
            job.completed_at = datetime.utcnow()
            job.error_message = (
                f"Job stuck in {job.status} status for more than "
                f"{stuck_threshold_minutes} minutes. Marked as failed by watchdog."
            )
            stuck_job_ids.append(str(job.id))

            # TODO: Optionally cancel the Celery task if it's still running
            # if job.celery_task_id:
            #     celery_app.control.revoke(job.celery_task_id, terminate=True)

        self.db.commit()

        if stuck_count > 0:
            logger.warning(f"⚠️  Found and marked {stuck_count} stuck jobs as failed")
        else:
            logger.info("✅ No stuck jobs found")

        return {
            "status": "completed",
            "stuck_count": stuck_count,
            "stuck_job_ids": stuck_job_ids,
            "cutoff_time": cutoff_time.isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Stuck job check failed: {e}")
        self.db.rollback()
        raise


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="app.tasks.maintenance_tasks.get_queue_stats",
)
def get_queue_stats(self) -> Dict[str, Any]:
    """
    Get statistics about job queues.

    Returns:
        Dict with queue statistics
    """
    try:
        # Count jobs by status
        pending_count = self.db.query(ProcessingJob).filter(
            ProcessingJob.status == "pending"
        ).count()

        running_count = self.db.query(ProcessingJob).filter(
            ProcessingJob.status == "running"
        ).count()

        completed_count = self.db.query(ProcessingJob).filter(
            ProcessingJob.status == "completed"
        ).count()

        failed_count = self.db.query(ProcessingJob).filter(
            ProcessingJob.status == "failed"
        ).count()

        # Count jobs by type
        proxy_gen_count = self.db.query(ProcessingJob).filter(
            ProcessingJob.job_type == "proxy_generation"
        ).count()

        cv_analysis_count = self.db.query(ProcessingJob).filter(
            ProcessingJob.job_type == "cv_analysis"
        ).count()

        return {
            "status_counts": {
                "pending": pending_count,
                "running": running_count,
                "completed": completed_count,
                "failed": failed_count,
            },
            "type_counts": {
                "proxy_generation": proxy_gen_count,
                "cv_analysis": cv_analysis_count,
            },
            "total": pending_count + running_count + completed_count + failed_count,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Queue stats failed: {e}")
        raise
