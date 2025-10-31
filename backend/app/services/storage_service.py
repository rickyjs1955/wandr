"""
Object storage service for video file management.

Provides a unified interface for S3-compatible storage (MinIO/AWS S3):
- Bucket initialization and management
- Multipart upload with presigned URLs
- File upload/download operations
- Signed URL generation for secure access
"""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import timedelta
from urllib.parse import urlparse

from minio import Minio
from minio.error import S3Error
from minio.commonconfig import ENABLED
from minio.versioningconfig import VersioningConfig

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """S3-compatible object storage service using MinIO."""

    def __init__(self):
        """Initialize MinIO client."""
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self.bucket_name = settings.MINIO_BUCKET
        self.initialized = False

    def initialize_bucket(self) -> None:
        """
        Initialize storage bucket with proper configuration.

        Creates bucket if it doesn't exist and sets up:
        - Bucket creation
        - Versioning (optional, disabled for MVP)
        - Lifecycle policies (future enhancement)
        """
        try:
            # Check if bucket exists
            if not self.client.bucket_exists(self.bucket_name):
                logger.info(f"Creating bucket: {self.bucket_name}")
                self.client.make_bucket(self.bucket_name)
                logger.info(f"✅ Bucket created: {self.bucket_name}")
            else:
                logger.info(f"✅ Bucket already exists: {self.bucket_name}")

            # Note: Versioning disabled for MVP to save storage
            # Can be enabled later: self.client.set_bucket_versioning(...)

            self.initialized = True

        except S3Error as e:
            logger.error(f"❌ Failed to initialize bucket: {e}")
            raise RuntimeError(f"Storage initialization failed: {e}")

    def ensure_initialized(self) -> None:
        """Ensure bucket is initialized before operations."""
        if not self.initialized:
            self.initialize_bucket()

    # ========================================================================
    # Multipart Upload Operations (for large videos 100MB+)
    # ========================================================================

    def initiate_multipart_upload(
        self,
        object_name: str,
        content_type: str = "video/mp4",
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Initiate a multipart upload session.

        Args:
            object_name: S3 object key (e.g., "videos/mall-123/pin-456/video.mp4")
            content_type: MIME type of the file
            metadata: Optional custom metadata dict

        Returns:
            upload_id: Unique identifier for this multipart upload session

        Example:
            upload_id = storage.initiate_multipart_upload(
                "videos/mall-001/pin-002/recording.mp4",
                metadata={"mall_id": "001", "pin_id": "002"}
            )
        """
        self.ensure_initialized()

        try:
            # MinIO doesn't have a direct initiate_multipart_upload method
            # We'll use presigned PUT URL approach instead
            # Return a session identifier that we'll track in the database
            import uuid
            upload_id = str(uuid.uuid4())

            logger.info(f"Initiated multipart upload: {object_name} (session: {upload_id})")
            return upload_id

        except S3Error as e:
            logger.error(f"Failed to initiate multipart upload: {e}")
            raise RuntimeError(f"Multipart upload initiation failed: {e}")

    def generate_presigned_upload_url(
        self,
        object_name: str,
        upload_id: str,
        part_number: int,
        expires: timedelta = timedelta(hours=1),
    ) -> str:
        """
        Generate presigned URL for uploading a single part.

        Args:
            object_name: S3 object key
            upload_id: Upload session ID to namespace the part (prevents collisions)
            part_number: Part number (1-indexed, max 10000)
            expires: URL expiration time (default 1 hour)

        Returns:
            presigned_url: URL for uploading the part

        Example:
            url = storage.generate_presigned_upload_url(
                "videos/recording.mp4",
                upload_id="abc-123",
                part_number=1
            )
            # Frontend uploads to this URL with PUT request
        """
        self.ensure_initialized()

        try:
            # Namespace part objects with upload_id to prevent collisions between
            # concurrent/retry uploads targeting the same final object
            part_object_name = f"{object_name}.{upload_id}.part{part_number}"

            url = self.client.presigned_put_object(
                self.bucket_name,
                part_object_name,
                expires=expires,
            )

            logger.debug(f"Generated presigned upload URL for part {part_number} (session {upload_id})")
            return url

        except S3Error as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise RuntimeError(f"Presigned URL generation failed: {e}")

    def complete_multipart_upload(
        self,
        object_name: str,
        upload_id: str,
        parts: List[Dict[str, any]],
    ) -> Dict[str, str]:
        """
        Complete a multipart upload by combining all parts.

        Args:
            object_name: Final S3 object key
            upload_id: Upload session ID from initiate_multipart_upload()
            parts: List of dicts with {"part_number": int, "etag": str}

        Returns:
            Dict with "object_name", "version_id", "etag"

        Example:
            result = storage.complete_multipart_upload(
                "videos/recording.mp4",
                upload_id="abc-123",
                parts=[
                    {"part_number": 1, "etag": "etag1"},
                    {"part_number": 2, "etag": "etag2"},
                ]
            )
        """
        self.ensure_initialized()

        try:
            # For MinIO with presigned URLs, we need to compose the parts
            # into a single object using compose_object
            from minio.commonconfig import ComposeSource

            sources = []
            for part in sorted(parts, key=lambda x: x["part_number"]):
                # Use namespaced part name matching generate_presigned_upload_url
                part_object_name = f"{object_name}.{upload_id}.part{part['part_number']}"
                sources.append(ComposeSource(self.bucket_name, part_object_name))

            # Compose all parts into final object
            result = self.client.compose_object(
                self.bucket_name,
                object_name,
                sources,
            )

            # Clean up part objects for this upload session only
            for part in parts:
                part_object_name = f"{object_name}.{upload_id}.part{part['part_number']}"
                try:
                    self.client.remove_object(self.bucket_name, part_object_name)
                except S3Error:
                    logger.warning(f"Failed to remove part object: {part_object_name}")

            logger.info(f"✅ Completed multipart upload: {object_name} (session {upload_id})")

            return {
                "object_name": object_name,
                "etag": result.etag,
                "version_id": result.version_id if result.version_id else None,
            }

        except S3Error as e:
            logger.error(f"Failed to complete multipart upload: {e}")
            raise RuntimeError(f"Multipart upload completion failed: {e}")

    def abort_multipart_upload(
        self,
        object_name: str,
        upload_id: str,
    ) -> None:
        """
        Abort a multipart upload and clean up parts.

        Args:
            object_name: S3 object key
            upload_id: Upload session ID from initiate_multipart_upload()

        Example:
            storage.abort_multipart_upload("videos/recording.mp4", "abc-123")
        """
        self.ensure_initialized()

        try:
            # Clean up only this upload session's part objects
            # Use upload_id-namespaced prefix to avoid deleting other sessions' parts
            objects = self.client.list_objects(
                self.bucket_name,
                prefix=f"{object_name}.{upload_id}.part",
            )

            for obj in objects:
                try:
                    self.client.remove_object(self.bucket_name, obj.object_name)
                except S3Error:
                    logger.warning(f"Failed to remove part object: {obj.object_name}")

            logger.info(f"✅ Aborted multipart upload: {object_name} (session {upload_id})")

        except S3Error as e:
            logger.error(f"Failed to abort multipart upload: {e}")
            # Don't raise - abort is best-effort cleanup

    # ========================================================================
    # Direct Upload Operations (for smaller files <100MB)
    # ========================================================================

    def upload_file(
        self,
        file_path: str,
        object_name: str,
        content_type: str = "video/mp4",
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        Upload a file directly to storage.

        Args:
            file_path: Local file path
            object_name: S3 object key
            content_type: MIME type
            metadata: Optional custom metadata

        Returns:
            Dict with "object_name", "etag", "size"

        Example:
            result = storage.upload_file(
                "/tmp/video.mp4",
                "videos/mall-001/video.mp4"
            )
        """
        self.ensure_initialized()

        try:
            result = self.client.fput_object(
                self.bucket_name,
                object_name,
                file_path,
                content_type=content_type,
                metadata=metadata,
            )

            logger.info(f"✅ Uploaded file: {object_name}")

            return {
                "object_name": result.object_name,
                "etag": result.etag,
                "version_id": result.version_id if result.version_id else None,
            }

        except S3Error as e:
            logger.error(f"Failed to upload file: {e}")
            raise RuntimeError(f"File upload failed: {e}")

    def download_file(
        self,
        object_name: str,
        file_path: str,
    ) -> str:
        """
        Download a file from storage.

        Args:
            object_name: S3 object key
            file_path: Local destination path

        Returns:
            file_path: Path to downloaded file

        Example:
            path = storage.download_file(
                "videos/recording.mp4",
                "/tmp/recording.mp4"
            )
        """
        self.ensure_initialized()

        try:
            self.client.fget_object(
                self.bucket_name,
                object_name,
                file_path,
            )

            logger.info(f"✅ Downloaded file: {object_name} -> {file_path}")
            return file_path

        except S3Error as e:
            logger.error(f"Failed to download file: {e}")
            raise RuntimeError(f"File download failed: {e}")

    # ========================================================================
    # Signed URL Operations (for secure video streaming)
    # ========================================================================

    def generate_presigned_get_url(
        self,
        object_name: str,
        expires: timedelta = timedelta(hours=1),
    ) -> str:
        """
        Generate presigned URL for downloading/streaming a file.

        Args:
            object_name: S3 object key
            expires: URL expiration time (default 1 hour)

        Returns:
            presigned_url: URL for accessing the file

        Example:
            url = storage.generate_presigned_get_url("videos/recording.mp4")
            # Frontend can stream video from this URL
        """
        self.ensure_initialized()

        try:
            url = self.client.presigned_get_object(
                self.bucket_name,
                object_name,
                expires=expires,
            )

            logger.debug(f"Generated presigned GET URL: {object_name}")
            return url

        except S3Error as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise RuntimeError(f"Presigned URL generation failed: {e}")

    # ========================================================================
    # File Management Operations
    # ========================================================================

    def delete_file(self, object_name: str) -> None:
        """
        Delete a file from storage.

        Args:
            object_name: S3 object key

        Example:
            storage.delete_file("videos/old-recording.mp4")
        """
        self.ensure_initialized()

        try:
            self.client.remove_object(self.bucket_name, object_name)
            logger.info(f"✅ Deleted file: {object_name}")

        except S3Error as e:
            logger.error(f"Failed to delete file: {e}")
            raise RuntimeError(f"File deletion failed: {e}")

    def file_exists(self, object_name: str) -> bool:
        """
        Check if a file exists in storage.

        Args:
            object_name: S3 object key

        Returns:
            exists: True if file exists

        Example:
            if storage.file_exists("videos/recording.mp4"):
                print("File exists")
        """
        self.ensure_initialized()

        try:
            self.client.stat_object(self.bucket_name, object_name)
            return True

        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            logger.error(f"Failed to check file existence: {e}")
            raise RuntimeError(f"File existence check failed: {e}")

    def get_file_metadata(self, object_name: str) -> Dict[str, any]:
        """
        Get file metadata (size, content-type, etag, etc).

        Args:
            object_name: S3 object key

        Returns:
            metadata: Dict with file information

        Example:
            meta = storage.get_file_metadata("videos/recording.mp4")
            print(f"Size: {meta['size']} bytes")
        """
        self.ensure_initialized()

        try:
            stat = self.client.stat_object(self.bucket_name, object_name)

            return {
                "object_name": stat.object_name,
                "size": stat.size,
                "etag": stat.etag,
                "content_type": stat.content_type,
                "last_modified": stat.last_modified,
                "metadata": stat.metadata,
                "version_id": stat.version_id if stat.version_id else None,
            }

        except S3Error as e:
            logger.error(f"Failed to get file metadata: {e}")
            raise RuntimeError(f"File metadata retrieval failed: {e}")

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def generate_object_path(
        self,
        mall_id: str,
        pin_id: str,
        filename: str,
        path_type: str = "original",
    ) -> str:
        """
        Generate standardized S3 object path.

        Args:
            mall_id: Mall UUID
            pin_id: Camera pin UUID
            filename: Original filename
            path_type: "original" or "proxy"

        Returns:
            object_path: S3 key like "videos/mall-123/pin-456/original/filename.mp4"

        Example:
            path = storage.generate_object_path(
                "mall-001",
                "pin-002",
                "recording_20251031.mp4",
                path_type="original"
            )
        """
        # Remove any directory components from filename
        import os
        clean_filename = os.path.basename(filename)

        return f"videos/{mall_id}/{pin_id}/{path_type}/{clean_filename}"


# ========================================================================
# Singleton Instance
# ========================================================================

# Global storage service instance
_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """
    Get singleton storage service instance.

    Returns:
        storage_service: Initialized storage service

    Example:
        storage = get_storage_service()
        storage.upload_file("/tmp/video.mp4", "videos/recording.mp4")
    """
    global _storage_service

    if _storage_service is None:
        _storage_service = StorageService()
        _storage_service.initialize_bucket()

    return _storage_service
