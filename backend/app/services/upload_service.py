"""
Video upload service for multipart upload management.

Handles:
- Upload session initialization
- Part URL generation
- Upload completion and validation
- Upload abortion and cleanup
- Upload state tracking
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import Video, Mall, CameraPin
from app.services.storage_service import get_storage_service
from app.core.config import settings

logger = logging.getLogger(__name__)


class UploadService:
    """Service for managing multipart video uploads."""

    # Upload session expiry (4 hours by default)
    UPLOAD_SESSION_EXPIRY_HOURS = 4

    # Part URL expiry (1 hour by default)
    PART_URL_EXPIRY_HOURS = 1

    def __init__(self, db: Session):
        """Initialize upload service with database session."""
        self.db = db
        self.storage = get_storage_service()

    # ========================================================================
    # Upload Session Management
    # ========================================================================

    def initiate_upload(
        self,
        mall_id: UUID,
        pin_id: UUID,
        filename: str,
        file_size_bytes: int,
        content_type: str = "video/mp4",
        checksum_sha256: Optional[str] = None,
        recorded_at: Optional[datetime] = None,
        operator_notes: Optional[str] = None,
        uploaded_by_user_id: Optional[UUID] = None,
        video_width: Optional[int] = None,
        video_height: Optional[int] = None,
        video_fps: Optional[float] = None,
        video_duration_seconds: Optional[int] = None,
    ) -> Tuple[UUID, UUID, datetime]:
        """
        Initiate a multipart upload session.

        Creates:
        1. Video database record with upload_status='uploading'
        2. S3 multipart upload session
        3. Returns upload_id, video_id, and expiry time

        Args:
            mall_id: Mall UUID
            pin_id: Camera pin UUID
            filename: Original filename
            file_size_bytes: Total file size
            content_type: MIME type
            checksum_sha256: Optional SHA256 checksum for validation
            recorded_at: When video was recorded
            operator_notes: Optional notes
            uploaded_by_user_id: User performing upload
            video_width: Video width in pixels
            video_height: Video height in pixels
            video_fps: Video frame rate
            video_duration_seconds: Video duration

        Returns:
            Tuple of (upload_id, video_id, expires_at)

        Raises:
            ValueError: If mall_id or pin_id doesn't exist
            RuntimeError: If storage operation fails
        """
        # Validate mall and pin exist
        mall = self.db.query(Mall).filter(Mall.id == mall_id).first()
        if not mall:
            raise ValueError(f"Mall {mall_id} not found")

        pin = self.db.query(CameraPin).filter(
            and_(CameraPin.id == pin_id, CameraPin.mall_id == mall_id)
        ).first()
        if not pin:
            raise ValueError(f"Camera pin {pin_id} not found in mall {mall_id}")

        # Generate object path
        object_path = self.storage.generate_object_path(
            str(mall_id),
            str(pin_id),
            filename,
            path_type="original",
        )

        # Create video database record
        video = Video(
            id=uuid4(),
            mall_id=mall_id,
            pin_id=pin_id,
            camera_pin_id=pin_id,  # Legacy field
            filename=filename,
            original_filename=filename,  # Legacy field
            file_path=object_path,  # Will be S3 path
            original_path=object_path,
            file_size_bytes=file_size_bytes,
            content_type=content_type,
            checksum_sha256=checksum_sha256,
            recorded_at=recorded_at,
            operator_notes=operator_notes,
            uploaded_by_user_id=uploaded_by_user_id,
            upload_status="uploading",
            video_width=video_width,
            video_height=video_height,
            video_fps=video_fps,
            video_duration_seconds=video_duration_seconds,
            uploaded_at=None,  # Will be set on completion
            processing_status="pending",
            processed=False,  # Legacy field
        )

        self.db.add(video)
        self.db.commit()
        self.db.refresh(video)

        # Initiate S3 multipart upload
        try:
            upload_id_str = self.storage.initiate_multipart_upload(
                object_path,
                content_type=content_type,
                metadata={
                    "mall_id": str(mall_id),
                    "pin_id": str(pin_id),
                    "video_id": str(video.id),
                    "filename": filename,
                },
            )
            upload_id = UUID(upload_id_str)

        except Exception as e:
            # Rollback video record if storage operation fails
            self.db.delete(video)
            self.db.commit()
            raise RuntimeError(f"Failed to initiate S3 upload: {e}")

        # Calculate expiry
        expires_at = datetime.utcnow() + timedelta(hours=self.UPLOAD_SESSION_EXPIRY_HOURS)

        logger.info(
            f"Initiated upload session: video_id={video.id}, upload_id={upload_id}, "
            f"file={filename}, size={file_size_bytes}"
        )

        return upload_id, video.id, expires_at

    def generate_part_url(
        self,
        upload_id: UUID,
        video_id: UUID,
        part_number: int,
    ) -> Tuple[str, datetime]:
        """
        Generate presigned URL for uploading a specific part.

        Args:
            upload_id: Upload session UUID
            video_id: Video UUID
            part_number: Part number (1-10000)

        Returns:
            Tuple of (presigned_url, expires_at)

        Raises:
            ValueError: If video doesn't exist or is not in uploading status
        """
        # Verify video exists and is in uploading status
        video = self.db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise ValueError(f"Video {video_id} not found")

        if video.upload_status != "uploading":
            raise ValueError(
                f"Video {video_id} is not in uploading status (current: {video.upload_status})"
            )

        # Generate presigned URL
        expires = timedelta(hours=self.PART_URL_EXPIRY_HOURS)
        presigned_url = self.storage.generate_presigned_upload_url(
            video.original_path,
            part_number=part_number,
            expires=expires,
        )

        expires_at = datetime.utcnow() + expires

        logger.debug(
            f"Generated part URL: video_id={video_id}, upload_id={upload_id}, "
            f"part={part_number}"
        )

        return presigned_url, expires_at

    def complete_upload(
        self,
        upload_id: UUID,
        video_id: UUID,
        parts: List[Dict[str, any]],
        final_checksum_sha256: Optional[str] = None,
    ) -> Dict[str, any]:
        """
        Complete a multipart upload.

        Validates checksums, combines parts, updates video record.

        Args:
            upload_id: Upload session UUID
            video_id: Video UUID
            parts: List of dicts with part_number and etag
            final_checksum_sha256: Optional final checksum for validation

        Returns:
            Dict with completion details

        Raises:
            ValueError: If video doesn't exist, wrong status, or checksum mismatch
            RuntimeError: If storage operation fails
        """
        # Get video record
        video = self.db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise ValueError(f"Video {video_id} not found")

        if video.upload_status != "uploading":
            raise ValueError(
                f"Video {video_id} is not in uploading status (current: {video.upload_status})"
            )

        # Validate checksum if provided
        if final_checksum_sha256:
            if video.checksum_sha256 and video.checksum_sha256 != final_checksum_sha256:
                logger.error(
                    f"Checksum mismatch for video {video_id}: "
                    f"expected={video.checksum_sha256}, got={final_checksum_sha256}"
                )
                # Mark upload as failed
                video.upload_status = "failed"
                video.error_message = "Checksum validation failed"
                self.db.commit()
                raise ValueError("Checksum validation failed")

            # Update checksum if not set initially
            if not video.checksum_sha256:
                video.checksum_sha256 = final_checksum_sha256

        # Complete S3 multipart upload
        try:
            result = self.storage.complete_multipart_upload(
                video.original_path,
                str(upload_id),
                parts,
            )

            # Update video record
            video.upload_status = "uploaded"
            video.uploaded_at = datetime.utcnow()
            video.s3_etag = result.get("etag")
            video.s3_version_id = result.get("version_id")

            self.db.commit()
            self.db.refresh(video)

            logger.info(
                f"✅ Completed upload: video_id={video_id}, upload_id={upload_id}, "
                f"parts={len(parts)}, size={video.file_size_bytes}"
            )

            return {
                "video_id": video.id,
                "upload_id": upload_id,
                "object_path": video.original_path,
                "file_size_bytes": video.file_size_bytes,
                "checksum_sha256": video.checksum_sha256,
                "etag": result.get("etag"),
            }

        except Exception as e:
            # Mark upload as failed
            video.upload_status = "failed"
            video.error_message = str(e)
            self.db.commit()
            raise RuntimeError(f"Failed to complete S3 upload: {e}")

    def abort_upload(
        self,
        upload_id: UUID,
        video_id: UUID,
        reason: Optional[str] = None,
    ) -> int:
        """
        Abort a multipart upload and clean up.

        Args:
            upload_id: Upload session UUID
            video_id: Video UUID
            reason: Optional reason for aborting

        Returns:
            Number of parts cleaned up

        Raises:
            ValueError: If video doesn't exist
        """
        # Get video record
        video = self.db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise ValueError(f"Video {video_id} not found")

        # Abort S3 multipart upload (best-effort cleanup)
        parts_cleaned = 0
        try:
            self.storage.abort_multipart_upload(
                video.original_path,
                str(upload_id),
            )
            # Note: We don't track exact part count, so returning 0
            # Real implementation would query S3 for part list first

        except Exception as e:
            logger.warning(f"Failed to abort S3 upload: {e}")

        # Update video record
        video.upload_status = "aborted"
        if reason:
            video.error_message = f"Aborted: {reason}"

        self.db.commit()

        logger.info(
            f"Aborted upload: video_id={video_id}, upload_id={upload_id}, "
            f"reason={reason or 'not specified'}"
        )

        return parts_cleaned

    def get_upload_status(
        self,
        upload_id: UUID,
        video_id: UUID,
    ) -> Dict[str, any]:
        """
        Get current status of an upload session.

        Args:
            upload_id: Upload session UUID
            video_id: Video UUID

        Returns:
            Dict with upload status details

        Raises:
            ValueError: If video doesn't exist
        """
        video = self.db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise ValueError(f"Video {video_id} not found")

        # Calculate expiry (4 hours from creation)
        expires_at = video.created_at + timedelta(hours=self.UPLOAD_SESSION_EXPIRY_HOURS)

        return {
            "upload_id": upload_id,
            "video_id": video.id,
            "status": video.upload_status,
            "mall_id": video.mall_id,
            "pin_id": video.pin_id,
            "filename": video.filename,
            "file_size_bytes": video.file_size_bytes,
            "uploaded_bytes": 0,  # TODO: Track actual uploaded bytes
            "parts_uploaded": 0,  # TODO: Track actual parts
            "parts_total": None,  # Not tracked
            "created_at": video.created_at,
            "expires_at": expires_at,
            "completed_at": video.uploaded_at,
            "error_message": video.error_message,
        }

    # ========================================================================
    # Deduplication
    # ========================================================================

    def check_duplicate(
        self,
        mall_id: UUID,
        pin_id: UUID,
        checksum_sha256: str,
    ) -> Optional[Video]:
        """
        Check if video with same checksum already exists for this pin.

        Args:
            mall_id: Mall UUID
            pin_id: Camera pin UUID
            checksum_sha256: SHA256 checksum

        Returns:
            Existing Video if found, None otherwise
        """
        video = self.db.query(Video).filter(
            and_(
                Video.mall_id == mall_id,
                Video.pin_id == pin_id,
                Video.checksum_sha256 == checksum_sha256,
                Video.upload_status.in_(["uploaded", "uploading"]),
            )
        ).first()

        if video:
            logger.info(
                f"Duplicate video detected: checksum={checksum_sha256}, "
                f"existing_video_id={video.id}"
            )

        return video


def get_upload_service(db: Session) -> UploadService:
    """
    Dependency for getting upload service instance.

    Args:
        db: Database session

    Returns:
        UploadService instance
    """
    return UploadService(db)
