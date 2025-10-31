"""
Processing job service for background task management.

Handles:
- Job creation and tracking
- Job status queries
- Job cancellation
- Job result retrieval
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models import ProcessingJob, Video
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


class JobService:
    """Service for managing background processing jobs."""

    def __init__(self, db: Session):
        """Initialize job service with database session."""
        self.db = db

    # ========================================================================
    # Job Creation
    # ========================================================================

    def create_job(
        self,
        video_id: UUID,
        job_type: str,
        parameters: Optional[Dict] = None,
    ) -> ProcessingJob:
        """
        Create a new processing job.

        Args:
            video_id: Video UUID
            job_type: Type of job ('proxy_generation', 'cv_analysis', etc.)
            parameters: Optional job parameters (stored in JSONB)

        Returns:
            ProcessingJob record

        Raises:
            ValueError: If video doesn't exist
        """
        # Verify video exists
        video = self.db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise ValueError(f"Video {video_id} not found")

        # Create job record
        # Note: parameters column doesn't exist in ProcessingJob model
        # Use result_data for job configuration if needed, or add parameters column in future migration
        job = ProcessingJob(
            id=uuid4(),
            video_id=video_id,
            job_type=job_type,
            status="pending",
            # queued_at: let DB default populate (avoids clock skew)
        )

        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        logger.info(
            f"Created processing job: job_id={job.id}, type={job_type}, video_id={video_id}"
        )

        return job

    def queue_proxy_generation(
        self,
        video_id: UUID,
        priority: int = 5,
    ) -> ProcessingJob:
        """
        Queue a proxy generation job for a video.

        Args:
            video_id: Video UUID
            priority: Task priority (1-10, default 5)

        Returns:
            ProcessingJob record with celery_task_id
        """
        # Create job record (parameters removed - see create_job)
        job = self.create_job(
            video_id=video_id,
            job_type="proxy_generation",
        )

        # Update video processing_status to reflect that processing has been queued
        video = self.db.query(Video).filter(Video.id == video_id).first()
        if video:
            video.processing_status = "processing"
            video.processing_job_id = str(job.id)

        # Queue Celery task
        from app.tasks.video_tasks import generate_proxy_video

        task = generate_proxy_video.apply_async(
            args=[str(video_id), str(job.id)],
            queue="video_processing",
            priority=priority,
        )

        # Update job with Celery task ID
        job.celery_task_id = task.id
        self.db.commit()
        self.db.refresh(job)

        logger.info(
            f"Queued proxy generation: job_id={job.id}, task_id={task.id}, video_id={video_id}"
        )

        return job

    # ========================================================================
    # Job Queries
    # ========================================================================

    def get_job(self, job_id: UUID) -> Optional[ProcessingJob]:
        """
        Get job by ID.

        Args:
            job_id: Job UUID

        Returns:
            ProcessingJob or None if not found
        """
        return self.db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()

    def get_jobs_for_video(
        self,
        video_id: UUID,
        job_type: Optional[str] = None,
    ) -> List[ProcessingJob]:
        """
        Get all jobs for a video.

        Args:
            video_id: Video UUID
            job_type: Optional filter by job type

        Returns:
            List of ProcessingJob records
        """
        query = self.db.query(ProcessingJob).filter(ProcessingJob.video_id == video_id)

        if job_type:
            query = query.filter(ProcessingJob.job_type == job_type)

        return query.order_by(desc(ProcessingJob.queued_at)).all()

    def get_job_status(self, job_id: UUID) -> Dict:
        """
        Get detailed job status.

        Args:
            job_id: Job UUID

        Returns:
            Dict with job status details

        Raises:
            ValueError: If job not found
        """
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Calculate duration if applicable
        duration_seconds = None
        if job.started_at and job.completed_at:
            duration_seconds = (job.completed_at - job.started_at).total_seconds()
        elif job.started_at:
            duration_seconds = (datetime.utcnow() - job.started_at).total_seconds()

        return {
            "job_id": str(job.id),
            "video_id": str(job.video_id),
            "job_type": job.job_type,
            "status": job.status,
            "celery_task_id": job.celery_task_id,
            "queued_at": job.queued_at.isoformat() if job.queued_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "duration_seconds": duration_seconds,
            "error_message": job.error_message,
            "result_data": job.result_data,
            # Note: parameters column doesn't exist, removed from response
        }

    def get_pending_jobs(
        self,
        job_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[ProcessingJob]:
        """
        Get pending jobs.

        Args:
            job_type: Optional filter by job type
            limit: Maximum number of jobs to return

        Returns:
            List of pending ProcessingJob records
        """
        query = self.db.query(ProcessingJob).filter(ProcessingJob.status == "pending")

        if job_type:
            query = query.filter(ProcessingJob.job_type == job_type)

        return query.order_by(ProcessingJob.queued_at).limit(limit).all()

    # ========================================================================
    # Job Cancellation
    # ========================================================================

    def cancel_job(self, job_id: UUID, reason: Optional[str] = None) -> bool:
        """
        Cancel a running or pending job.

        Args:
            job_id: Job UUID
            reason: Optional cancellation reason

        Returns:
            True if cancelled, False if already completed/failed

        Raises:
            ValueError: If job not found
        """
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Can only cancel pending or running jobs
        if job.status not in ["pending", "running"]:
            logger.warning(
                f"Cannot cancel job {job_id} with status {job.status}"
            )
            return False

        # Revoke Celery task if exists
        if job.celery_task_id:
            celery_app.control.revoke(
                job.celery_task_id,
                terminate=True,
                signal="SIGKILL",
            )
            logger.info(f"Revoked Celery task: {job.celery_task_id}")

        # Update job status
        job.status = "failed"
        job.completed_at = datetime.utcnow()
        job.error_message = f"Cancelled by user: {reason or 'No reason provided'}"

        self.db.commit()

        logger.info(f"Cancelled job: job_id={job_id}, reason={reason}")

        return True

    # ========================================================================
    # Job Cleanup
    # ========================================================================

    def delete_old_jobs(self, days: int = 30) -> int:
        """
        Delete old completed/failed jobs.

        Args:
            days: Delete jobs older than N days

        Returns:
            Number of jobs deleted
        """
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(days=days)

        jobs = (
            self.db.query(ProcessingJob)
            .filter(
                and_(
                    ProcessingJob.status.in_(["completed", "failed"]),
                    ProcessingJob.completed_at < cutoff,
                )
            )
            .all()
        )

        count = len(jobs)

        for job in jobs:
            self.db.delete(job)

        self.db.commit()

        logger.info(f"Deleted {count} old processing jobs")

        return count


def get_job_service(db: Session) -> JobService:
    """
    Dependency for getting job service instance.

    Args:
        db: Database session

    Returns:
        JobService instance
    """
    return JobService(db)
