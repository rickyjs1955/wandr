"""
Video processing tasks.

Celery tasks for video operations:
- Proxy video generation (480p, 10fps)
- Video metadata extraction
- Thumbnail generation
"""
import logging
from uuid import UUID
from typing import Dict, Any

from celery import Task
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models import Video, ProcessingJob
from app.services.storage_service import get_storage_service

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
    name="app.tasks.video_tasks.generate_proxy_video",
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
)
def generate_proxy_video(
    self,
    video_id: str,
    job_id: str,
) -> Dict[str, Any]:
    """
    Generate proxy video (480p, 10fps) for streaming.

    This is a placeholder task for Phase 2.4.
    Full implementation will be in Phase 2.5 with FFmpeg integration.

    Args:
        video_id: Video UUID (as string)
        job_id: ProcessingJob UUID (as string)

    Returns:
        Dict with job result details

    Raises:
        Exception: On FFmpeg or storage errors (triggers retry)
    """
    video_uuid = UUID(video_id)
    job_uuid = UUID(job_id)

    logger.info(f"Starting proxy generation: video_id={video_id}, job_id={job_id}")

    try:
        # Get video and job records
        video = self.db.query(Video).filter(Video.id == video_uuid).first()
        if not video:
            raise ValueError(f"Video {video_id} not found")

        job = self.db.query(ProcessingJob).filter(ProcessingJob.id == job_uuid).first()
        if not job:
            raise ValueError(f"ProcessingJob {job_id} not found")

        # Update job status
        job.status = "running"
        job.started_at = self.db.execute("SELECT NOW()").scalar()
        job.celery_task_id = self.request.id
        self.db.commit()

        # TODO: Phase 2.5 - Implement actual proxy generation
        # 1. Download original video from S3
        # 2. Run FFmpeg to create proxy (480p, 10fps)
        # 3. Upload proxy to S3
        # 4. Extract video metadata (width, height, fps, codec, duration)
        # 5. Generate thumbnail

        # For Phase 2.4, just simulate success
        logger.info(f"[PLACEHOLDER] Proxy generation simulated for video {video_id}")

        # Update video record (placeholder values)
        video.proxy_path = video.original_path.replace("/original/", "/proxy/")
        # Note: proxy_generated column doesn't exist in Video model
        # Phase 2.5 will either add this column or use a different approach to track proxy status

        # Update video processing_status to reflect task completion
        video.processing_status = "completed"
        video.processing_completed_at = self.db.execute("SELECT NOW()").scalar()
        self.db.commit()

        # Update job status
        job.status = "completed"
        job.completed_at = self.db.execute("SELECT NOW()").scalar()
        job.result_data = {
            "status": "placeholder",
            "message": "Proxy generation will be implemented in Phase 2.5",
            "video_id": str(video.id),
        }
        self.db.commit()

        logger.info(f"✅ Proxy generation job completed: video_id={video_id}, job_id={job_id}")

        return {
            "status": "completed",
            "video_id": str(video.id),
            "job_id": str(job.id),
        }

    except Exception as e:
        logger.error(f"❌ Proxy generation failed: video_id={video_id}, error={e}")

        # Update video processing_status to failed
        video = self.db.query(Video).filter(Video.id == video_uuid).first()
        if video:
            video.processing_status = "failed"
            video.processing_error = str(e)

        # Update job status to failed
        job = self.db.query(ProcessingJob).filter(ProcessingJob.id == job_uuid).first()
        if job:
            job.status = "failed"
            job.completed_at = self.db.execute("SELECT NOW()").scalar()
            job.error_message = str(e)
            self.db.commit()

        # Retry on transient errors
        if self.request.retries < self.max_retries:
            logger.info(
                f"Retrying proxy generation (attempt {self.request.retries + 1}/{self.max_retries})"
            )
            raise self.retry(exc=e)

        # Give up after max retries
        raise


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="app.tasks.video_tasks.extract_video_metadata",
    max_retries=2,
)
def extract_video_metadata(
    self,
    video_id: str,
) -> Dict[str, Any]:
    """
    Extract video metadata using FFprobe.

    This is a placeholder task for Phase 2.5.

    Args:
        video_id: Video UUID (as string)

    Returns:
        Dict with video metadata (width, height, fps, duration, codec)
    """
    logger.info(f"[PLACEHOLDER] Extracting metadata for video {video_id}")

    # TODO: Phase 2.5 - Implement FFprobe integration
    # 1. Download video from S3 (or use presigned URL)
    # 2. Run FFprobe to extract metadata
    # 3. Update video record with metadata
    # 4. Return metadata dict

    return {
        "status": "placeholder",
        "message": "Metadata extraction will be implemented in Phase 2.5",
        "video_id": video_id,
    }


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="app.tasks.video_tasks.generate_thumbnail",
    max_retries=2,
)
def generate_thumbnail(
    self,
    video_id: str,
    timestamp_seconds: float = 5.0,
) -> Dict[str, Any]:
    """
    Generate thumbnail image from video.

    This is a placeholder task for Phase 2.5.

    Args:
        video_id: Video UUID (as string)
        timestamp_seconds: Which timestamp to capture (default 5 seconds)

    Returns:
        Dict with thumbnail S3 path
    """
    logger.info(f"[PLACEHOLDER] Generating thumbnail for video {video_id} at {timestamp_seconds}s")

    # TODO: Phase 2.5 - Implement thumbnail generation
    # 1. Download video from S3 (or use presigned URL)
    # 2. Use FFmpeg to extract frame at timestamp
    # 3. Upload thumbnail to S3 (thumbnails/{video_id}.jpg)
    # 4. Update video record with thumbnail_path
    # 5. Return thumbnail path

    return {
        "status": "placeholder",
        "message": "Thumbnail generation will be implemented in Phase 2.5",
        "video_id": video_id,
    }
