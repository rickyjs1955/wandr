"""
Video service for video management operations.

Handles:
- Video listing with filters and pagination
- Video details retrieval
- Presigned URL generation for streaming
- Video deletion (with cleanup of all associated files)
"""
import logging
from typing import List, Optional, Tuple
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import Video, CameraPin, Mall, ProcessingJob
from app.services.storage_service import get_storage_service

logger = logging.getLogger(__name__)


class VideoService:
    """Service for video management operations."""

    def __init__(self, db: Session):
        """
        Initialize video service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.storage = get_storage_service()

    def list_videos(
        self,
        mall_id: Optional[UUID] = None,
        pin_id: Optional[UUID] = None,
        processing_status: Optional[str] = None,
        has_proxy: Optional[bool] = None,
        uploaded_after: Optional[datetime] = None,
        uploaded_before: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Video], int]:
        """
        List videos with filters and pagination.

        Args:
            mall_id: Filter by mall ID
            pin_id: Filter by camera pin ID
            processing_status: Filter by processing status (pending, processing, completed, failed)
            has_proxy: Filter by proxy existence (True = has proxy, False = no proxy, None = all)
            uploaded_after: Filter videos uploaded after this datetime
            uploaded_before: Filter videos uploaded before this datetime
            page: Page number (1-indexed)
            page_size: Number of items per page (max 100)

        Returns:
            Tuple of (videos list, total count)
        """
        # Build query with eager loading
        query = self.db.query(Video).options(
            joinedload(Video.camera_pin).joinedload(CameraPin.mall)
        )

        # Apply filters
        if mall_id:
            query = query.join(CameraPin).filter(CameraPin.mall_id == mall_id)

        if pin_id:
            query = query.filter(Video.camera_pin_id == pin_id)

        if processing_status:
            query = query.filter(Video.processing_status == processing_status)

        if has_proxy is not None:
            if has_proxy:
                query = query.filter(Video.proxy_path.isnot(None))
            else:
                query = query.filter(Video.proxy_path.is_(None))

        if uploaded_after:
            query = query.filter(Video.uploaded_at >= uploaded_after)

        if uploaded_before:
            query = query.filter(Video.uploaded_at <= uploaded_before)

        # Get total count before pagination
        total = query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        videos = query.order_by(Video.uploaded_at.desc()).offset(offset).limit(page_size).all()

        return videos, total

    def get_video(self, video_id: UUID) -> Optional[Video]:
        """
        Get video by ID with eager loading of related entities.

        Args:
            video_id: Video UUID

        Returns:
            Video record or None if not found
        """
        return (
            self.db.query(Video)
            .options(
                joinedload(Video.camera_pin).joinedload(CameraPin.mall)
            )
            .filter(Video.id == video_id)
            .first()
        )

    def generate_stream_url(
        self,
        video_id: UUID,
        stream_type: str = "proxy",
        expires_minutes: int = 60,
    ) -> Optional[Tuple[str, datetime]]:
        """
        Generate presigned URL for video streaming.

        Args:
            video_id: Video UUID
            stream_type: Type of stream ("proxy" or "original")
            expires_minutes: URL expiration time in minutes (default: 60)

        Returns:
            Tuple of (presigned_url, expires_at) or None if video/file not found

        Raises:
            ValueError: If stream_type is invalid or file doesn't exist
        """
        video = self.get_video(video_id)
        if not video:
            return None

        # Determine which file to stream
        if stream_type == "proxy":
            if not video.proxy_path:
                raise ValueError("Proxy video not available (still processing or failed)")
            file_path = video.proxy_path
        elif stream_type == "original":
            file_path = video.original_path
        else:
            raise ValueError(f"Invalid stream_type: {stream_type}. Must be 'proxy' or 'original'")

        # Generate presigned URL
        expires_delta = timedelta(minutes=expires_minutes)
        presigned_url = self.storage.generate_presigned_get_url(
            file_path,
            expires=expires_delta,
        )

        expires_at = datetime.utcnow() + expires_delta

        logger.info(
            f"Generated {stream_type} stream URL for video {video_id}: {file_path} "
            f"(expires in {expires_minutes} minutes)"
        )

        return presigned_url, expires_at

    def generate_thumbnail_url(
        self,
        video_id: UUID,
        expires_minutes: int = 60,
    ) -> Optional[Tuple[str, datetime]]:
        """
        Generate presigned URL for thumbnail image.

        Args:
            video_id: Video UUID
            expires_minutes: URL expiration time in minutes (default: 60)

        Returns:
            Tuple of (presigned_url, expires_at) or None if video/thumbnail not found

        Raises:
            ValueError: If thumbnail doesn't exist
        """
        video = self.get_video(video_id)
        if not video:
            return None

        # Thumbnail path is deterministic: thumbnails/{mall_id}/{video_id}.jpg
        # Check processing job result_data for confirmation
        thumbnail_job = (
            self.db.query(ProcessingJob)
            .filter(ProcessingJob.video_id == video_id)
            .filter(ProcessingJob.job_type == "proxy_generation")
            .filter(ProcessingJob.status == "completed")
            .first()
        )

        if not thumbnail_job or not thumbnail_job.result_data:
            raise ValueError("Thumbnail not available (still processing or failed)")

        thumbnail_path = thumbnail_job.result_data.get("thumbnail_path")
        if not thumbnail_path:
            raise ValueError("Thumbnail not available (still processing or failed)")

        # Generate presigned URL
        expires_delta = timedelta(minutes=expires_minutes)
        presigned_url = self.storage.generate_presigned_get_url(
            thumbnail_path,
            expires=expires_delta,
        )

        expires_at = datetime.utcnow() + expires_delta

        logger.info(
            f"Generated thumbnail URL for video {video_id}: {thumbnail_path} "
            f"(expires in {expires_minutes} minutes)"
        )

        return presigned_url, expires_at

    def delete_video(
        self,
        video_id: UUID,
        delete_from_storage: bool = True,
    ) -> Tuple[bool, List[str]]:
        """
        Delete video and all associated files.

        Args:
            video_id: Video UUID
            delete_from_storage: If True, delete files from S3/MinIO (default: True)

        Returns:
            Tuple of (success: bool, deleted_files: List[str])

        Raises:
            ValueError: If video not found
        """
        video = self.get_video(video_id)
        if not video:
            raise ValueError(f"Video {video_id} not found")

        deleted_files = []

        # Delete files from storage if requested
        if delete_from_storage:
            files_to_delete = [video.original_path]

            if video.proxy_path:
                files_to_delete.append(video.proxy_path)

            # Get thumbnail path from processing job result_data
            thumbnail_job = (
                self.db.query(ProcessingJob)
                .filter(ProcessingJob.video_id == video_id)
                .filter(ProcessingJob.job_type == "proxy_generation")
                .filter(ProcessingJob.status == "completed")
                .first()
            )
            if thumbnail_job and thumbnail_job.result_data:
                thumbnail_path = thumbnail_job.result_data.get("thumbnail_path")
                if thumbnail_path:
                    files_to_delete.append(thumbnail_path)

            for file_path in files_to_delete:
                try:
                    self.storage.delete_file(file_path)
                    deleted_files.append(file_path)
                    logger.info(f"Deleted file from storage: {file_path}")
                except Exception as e:
                    logger.error(f"Failed to delete file {file_path}: {e}")
                    # Continue deleting other files even if one fails

        # Delete database record
        # Note: This will also delete related ProcessingJob records if cascade is set
        self.db.delete(video)
        self.db.commit()

        logger.info(
            f"Deleted video {video_id} from database. "
            f"Storage files deleted: {len(deleted_files)}/{len(files_to_delete) if delete_from_storage else 0}"
        )

        return True, deleted_files

    def get_video_stats(self, mall_id: Optional[UUID] = None) -> dict:
        """
        Get statistics about videos.

        Args:
            mall_id: Filter by mall ID (optional)

        Returns:
            Dict with video statistics:
            - total_videos: int
            - by_status: Dict[str, int]
            - total_storage_bytes: int
            - total_duration_seconds: float
        """
        query = self.db.query(Video)

        if mall_id:
            query = query.join(CameraPin).filter(CameraPin.mall_id == mall_id)

        total_videos = query.count()

        # Count by status
        status_counts = {}
        for status in ["pending", "processing", "completed", "failed"]:
            count = query.filter(Video.processing_status == status).count()
            status_counts[status] = count

        # Calculate total storage and duration
        stats = query.with_entities(
            func.sum(Video.file_size_bytes).label("total_bytes"),
            func.sum(Video.duration_seconds).label("total_duration"),
        ).first()

        total_storage_bytes = int(stats.total_bytes or 0)
        total_duration_seconds = float(stats.total_duration or 0)

        return {
            "total_videos": total_videos,
            "by_status": status_counts,
            "total_storage_bytes": total_storage_bytes,
            "total_duration_seconds": total_duration_seconds,
        }


# Dependency injection helper
def get_video_service(db: Session) -> VideoService:
    """
    Get or create video service instance.

    Args:
        db: SQLAlchemy database session

    Returns:
        VideoService instance
    """
    return VideoService(db)
