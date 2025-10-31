"""
Video processing tasks.

Celery tasks for video operations:
- Proxy video generation (480p, 10fps)
- Video metadata extraction
- Thumbnail generation
"""
import logging
import os
import tempfile
from uuid import UUID
from typing import Dict, Any
from pathlib import Path

from celery import Task
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models import Video, ProcessingJob
from app.services.storage_service import get_storage_service
from app.services.ffmpeg_service import get_ffmpeg_service

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

        # Get services
        storage = get_storage_service()
        ffmpeg = get_ffmpeg_service()

        # Create temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)

            # 1. Download original video from S3
            logger.info(f"Downloading original video from S3: {video.original_path}")
            original_local_path = temp_dir_path / f"original_{video.id}.mp4"
            storage.download_file(video.original_path, str(original_local_path))

            # Validate video file
            is_valid, error_msg = ffmpeg.validate_video(str(original_local_path))
            if not is_valid:
                raise ValueError(f"Invalid video file: {error_msg}")

            # 2. Extract metadata from original video
            logger.info("Extracting video metadata")
            metadata = ffmpeg.extract_metadata(str(original_local_path))

            # Update video with metadata
            video.width = metadata["width"]
            video.height = metadata["height"]
            video.fps = metadata["fps"]
            video.duration_seconds = metadata["duration_seconds"]
            video.codec = metadata["codec"]
            self.db.commit()

            # 3. Generate proxy video (480p, 10fps)
            logger.info("Generating proxy video (480p @ 10fps)")
            proxy_local_path = temp_dir_path / f"proxy_{video.id}.mp4"

            proxy_metadata = ffmpeg.generate_proxy(
                input_path=str(original_local_path),
                output_path=str(proxy_local_path),
                target_height=480,
                target_fps=10,
                preset="medium",  # Balance speed/quality
                crf=28,  # Medium quality for proxy
            )

            # 4. Upload proxy to S3
            proxy_s3_path = video.original_path.replace("/original/", "/proxy/")
            logger.info(f"Uploading proxy video to S3: {proxy_s3_path}")
            storage.upload_file(str(proxy_local_path), proxy_s3_path)

            # 5. Generate thumbnail (at 5 seconds)
            logger.info("Generating thumbnail")
            thumbnail_local_path = temp_dir_path / f"thumb_{video.id}.jpg"

            # Use 5 seconds or halfway point if video is shorter
            thumbnail_timestamp = min(5.0, metadata["duration_seconds"] / 2)

            thumbnail_metadata = ffmpeg.generate_thumbnail(
                input_path=str(original_local_path),
                output_path=str(thumbnail_local_path),
                timestamp_seconds=thumbnail_timestamp,
                width=320,
            )

            # Upload thumbnail to S3
            thumbnail_s3_path = f"thumbnails/{video.mall_id}/{video.id}.jpg"
            logger.info(f"Uploading thumbnail to S3: {thumbnail_s3_path}")
            storage.upload_file(
                str(thumbnail_local_path),
                thumbnail_s3_path,
                content_type="image/jpeg"  # Correct MIME type for thumbnails
            )

            # Update video record with proxy path
            video.proxy_path = proxy_s3_path
            # Note: thumbnail_path column doesn't exist in Video model
            # Thumbnail is tracked in job result_data for now
            video.processing_status = "completed"
            video.processing_completed_at = self.db.execute("SELECT NOW()").scalar()
            self.db.commit()

        # Update job status
        job.status = "completed"
        job.completed_at = self.db.execute("SELECT NOW()").scalar()
        job.result_data = {
            "status": "success",
            "proxy_path": proxy_s3_path,
            "thumbnail_path": thumbnail_s3_path,
            "metadata": {
                "original": metadata,
                "proxy": proxy_metadata,
                "thumbnail": thumbnail_metadata,
            },
        }
        self.db.commit()

        logger.info(
            f"✅ Proxy generation completed: video_id={video_id}, "
            f"proxy={proxy_s3_path}, thumbnail={thumbnail_s3_path}"
        )

        return {
            "status": "completed",
            "video_id": str(video.id),
            "job_id": str(job.id),
            "proxy_path": proxy_s3_path,
            "thumbnail_path": thumbnail_s3_path,
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

    Args:
        video_id: Video UUID (as string)

    Returns:
        Dict with video metadata (width, height, fps, duration, codec)
    """
    video_uuid = UUID(video_id)
    logger.info(f"Extracting metadata for video {video_id}")

    try:
        # Get video record
        video = self.db.query(Video).filter(Video.id == video_uuid).first()
        if not video:
            raise ValueError(f"Video {video_id} not found")

        # Get services
        storage = get_storage_service()
        ffmpeg = get_ffmpeg_service()

        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)

            # Download video from S3
            logger.info(f"Downloading video from S3: {video.original_path}")
            local_path = temp_dir_path / f"video_{video.id}.mp4"
            storage.download_file(video.original_path, str(local_path))

            # Extract metadata
            metadata = ffmpeg.extract_metadata(str(local_path))

            # Update video record
            video.width = metadata["width"]
            video.height = metadata["height"]
            video.fps = metadata["fps"]
            video.duration_seconds = metadata["duration_seconds"]
            video.codec = metadata["codec"]
            self.db.commit()

            logger.info(
                f"✅ Metadata extracted: {metadata['width']}x{metadata['height']} "
                f"@ {metadata['fps']:.2f}fps, {metadata['duration_seconds']:.1f}s"
            )

            return metadata

    except Exception as e:
        logger.error(f"❌ Metadata extraction failed: video_id={video_id}, error={e}")
        raise


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

    Args:
        video_id: Video UUID (as string)
        timestamp_seconds: Which timestamp to capture (default 5 seconds)

    Returns:
        Dict with thumbnail S3 path
    """
    video_uuid = UUID(video_id)
    logger.info(f"Generating thumbnail for video {video_id} at {timestamp_seconds}s")

    try:
        # Get video record
        video = self.db.query(Video).filter(Video.id == video_uuid).first()
        if not video:
            raise ValueError(f"Video {video_id} not found")

        # Get services
        storage = get_storage_service()
        ffmpeg = get_ffmpeg_service()

        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)

            # Download video from S3
            logger.info(f"Downloading video from S3: {video.original_path}")
            video_local_path = temp_dir_path / f"video_{video.id}.mp4"
            storage.download_file(video.original_path, str(video_local_path))

            # Generate thumbnail
            thumbnail_local_path = temp_dir_path / f"thumb_{video.id}.jpg"
            thumbnail_metadata = ffmpeg.generate_thumbnail(
                input_path=str(video_local_path),
                output_path=str(thumbnail_local_path),
                timestamp_seconds=timestamp_seconds,
                width=320,
            )

            # Upload thumbnail to S3
            thumbnail_s3_path = f"thumbnails/{video.mall_id}/{video.id}.jpg"
            logger.info(f"Uploading thumbnail to S3: {thumbnail_s3_path}")
            storage.upload_file(
                str(thumbnail_local_path),
                thumbnail_s3_path,
                content_type="image/jpeg"  # Correct MIME type for thumbnails
            )

            # Update video record
            # Note: thumbnail_path column doesn't exist in Video model
            # Thumbnail path is returned in task result for caller to store if needed
            self.db.commit()

            logger.info(f"✅ Thumbnail generated: {thumbnail_s3_path}")

            return {
                "status": "success",
                "thumbnail_path": thumbnail_s3_path,
                "metadata": thumbnail_metadata,
            }

    except Exception as e:
        logger.error(f"❌ Thumbnail generation failed: video_id={video_id}, error={e}")
        raise
