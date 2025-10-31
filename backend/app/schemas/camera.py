"""
Pydantic schemas for CameraPin and Video models.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# CameraPin schemas
class CameraPinBase(BaseModel):
    """Base camera pin schema."""
    name: str
    label: str
    location_lat: float = Field(..., ge=-90, le=90, description="Latitude coordinate")
    location_lng: float = Field(..., ge=-180, le=180, description="Longitude coordinate")
    pin_type: str = Field(default="normal", pattern="^(entrance|normal)$")
    mall_id: UUID


class CameraPinCreate(CameraPinBase):
    """Schema for creating a camera pin."""
    adjacent_to: List[UUID] = Field(default_factory=list)
    transit_times: Optional[Dict[str, Any]] = None
    store_id: Optional[UUID] = None
    camera_fps: int = Field(default=15, ge=1, le=60)
    camera_note: Optional[str] = None


class CameraPinUpdate(BaseModel):
    """Schema for updating a camera pin."""
    name: Optional[str] = None
    label: Optional[str] = None
    location_lat: Optional[float] = Field(None, ge=-90, le=90, description="Latitude coordinate")
    location_lng: Optional[float] = Field(None, ge=-180, le=180, description="Longitude coordinate")
    pin_type: Optional[str] = Field(None, pattern="^(entrance|normal)$")
    adjacent_to: Optional[List[UUID]] = None
    transit_times: Optional[Dict[str, Any]] = None
    store_id: Optional[UUID] = None
    camera_fps: Optional[int] = Field(None, ge=1, le=60)
    camera_note: Optional[str] = None


class CameraPin(CameraPinBase):
    """Schema for camera pin response."""
    id: UUID
    adjacent_to: List[UUID]
    transit_times: Optional[Dict[str, Any]] = None
    store_id: Optional[UUID] = None
    camera_fps: int
    camera_note: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Video schemas
class VideoBase(BaseModel):
    """Base video schema."""
    camera_pin_id: UUID


class VideoCreate(VideoBase):
    """Schema for creating a video record (after upload)."""
    file_path: str
    original_filename: str
    file_size_bytes: int = Field(..., gt=0, description="File size in bytes")
    duration_seconds: Optional[int] = None


class VideoUpdate(BaseModel):
    """Schema for updating a video."""
    processed: Optional[bool] = None
    processing_status: Optional[str] = Field(
        None, pattern="^(pending|processing|completed|failed)$"
    )
    duration_seconds: Optional[int] = None


class Video(VideoBase):
    """Schema for video response."""
    id: UUID
    file_path: str
    original_filename: str
    file_size_bytes: int
    duration_seconds: Optional[int] = None
    processed: bool
    processing_status: str
    upload_timestamp: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Video upload response
class VideoUploadResponse(BaseModel):
    """Schema for video upload response."""
    video: Video
    message: str = "Video uploaded successfully"


# ============================================================================
# Multipart Upload Schemas (Phase 2.3)
# ============================================================================

class MultipartUploadInitiateRequest(BaseModel):
    """
    Request schema for initiating a multipart upload.

    Client provides file metadata before starting the upload.
    """
    mall_id: UUID = Field(..., description="Mall ID where video belongs")
    pin_id: UUID = Field(..., description="Camera pin ID")
    filename: str = Field(..., min_length=1, max_length=255, description="Original filename")
    file_size_bytes: int = Field(..., gt=0, description="Total file size in bytes")
    content_type: str = Field(default="video/mp4", pattern="^video/.*", description="MIME type")
    checksum_sha256: Optional[str] = Field(
        None,
        min_length=64,
        max_length=64,
        pattern="^[a-fA-F0-9]{64}$",
        description="SHA256 checksum of entire file (hex string)"
    )
    recorded_at: Optional[datetime] = Field(None, description="When video was recorded")
    operator_notes: Optional[str] = Field(None, max_length=1000, description="Optional notes")

    # Video properties (if known)
    video_width: Optional[int] = Field(None, gt=0, le=7680, description="Video width in pixels")
    video_height: Optional[int] = Field(None, gt=0, le=4320, description="Video height in pixels")
    video_fps: Optional[float] = Field(None, gt=0, le=120, description="Video frames per second")
    video_duration_seconds: Optional[int] = Field(None, gt=0, description="Video duration in seconds")


class MultipartUploadInitiateResponse(BaseModel):
    """
    Response schema for initiated multipart upload.

    Returns upload_id and video_id for tracking the upload session.
    """
    upload_id: UUID = Field(..., description="Unique upload session ID")
    video_id: UUID = Field(..., description="Video database record ID")
    mall_id: UUID
    pin_id: UUID
    filename: str
    file_size_bytes: int
    checksum_required: bool = Field(
        default=True,
        description="Whether checksum validation will be performed"
    )
    expires_at: datetime = Field(..., description="When this upload session expires")
    message: str = Field(default="Multipart upload initiated. Use upload_id to request part URLs.")


class MultipartUploadPartUrlRequest(BaseModel):
    """
    Request schema for getting a presigned URL for a specific part.

    Client requests a URL for each part they want to upload.
    """
    part_number: int = Field(..., ge=1, le=10000, description="Part number (1-10000)")


class MultipartUploadPartUrlResponse(BaseModel):
    """
    Response schema with presigned URL for part upload.

    Client uses this URL to upload the part via PUT request.
    """
    upload_id: UUID
    part_number: int
    presigned_url: str = Field(..., description="Presigned URL for uploading this part")
    expires_at: datetime = Field(..., description="When this URL expires")
    instructions: str = Field(
        default="Upload this part using HTTP PUT to the presigned_url. Include Content-Type header."
    )


class MultipartUploadPartInfo(BaseModel):
    """
    Information about a single uploaded part.

    Client provides this after successfully uploading each part.
    """
    part_number: int = Field(..., ge=1, le=10000, description="Part number")
    etag: str = Field(..., min_length=1, description="ETag returned by S3 after upload")
    size_bytes: Optional[int] = Field(None, gt=0, description="Size of this part in bytes")


class MultipartUploadCompleteRequest(BaseModel):
    """
    Request schema for completing a multipart upload.

    Client provides list of all successfully uploaded parts.
    """
    parts: List[MultipartUploadPartInfo] = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="List of uploaded parts with their ETags"
    )
    final_checksum_sha256: Optional[str] = Field(
        None,
        min_length=64,
        max_length=64,
        pattern="^[a-fA-F0-9]{64}$",
        description="SHA256 checksum computed after upload (for validation)"
    )


class MultipartUploadCompleteResponse(BaseModel):
    """
    Response schema for completed multipart upload.

    Returns video details and processing job information.
    """
    video_id: UUID
    upload_id: UUID
    status: str = Field(default="completed", description="Upload status")
    object_path: str = Field(..., description="S3 object path")
    file_size_bytes: int
    checksum_sha256: Optional[str] = Field(None, description="Validated checksum")
    processing_job_id: Optional[UUID] = Field(
        None,
        description="Background job ID for proxy generation"
    )
    message: str = Field(
        default="Upload completed successfully. Video is queued for processing."
    )


class MultipartUploadAbortRequest(BaseModel):
    """
    Request schema for aborting a multipart upload.

    Optional reason for abort (for logging/debugging).
    """
    reason: Optional[str] = Field(None, max_length=500, description="Reason for aborting")


class MultipartUploadAbortResponse(BaseModel):
    """
    Response schema for aborted multipart upload.

    Confirms cleanup and provides status.
    """
    upload_id: UUID
    video_id: UUID
    status: str = Field(default="aborted", description="Upload status")
    parts_cleaned_up: int = Field(..., description="Number of part files cleaned up")
    message: str = Field(default="Upload aborted and cleaned up successfully.")


class MultipartUploadStatusResponse(BaseModel):
    """
    Response schema for upload status query.

    Allows client to check current state of an upload session.
    """
    upload_id: UUID
    video_id: UUID
    status: str = Field(
        ...,
        pattern="^(uploading|completed|aborted|failed)$",
        description="Current upload status"
    )
    mall_id: UUID
    pin_id: UUID
    filename: str
    file_size_bytes: int
    uploaded_bytes: int = Field(..., description="Bytes uploaded so far")
    parts_uploaded: int = Field(..., description="Number of parts uploaded")
    parts_total: Optional[int] = Field(None, description="Expected total parts (if known)")
    created_at: datetime
    expires_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


# ============================================================================
# Video Management Schemas (Phase 2.6)
# ============================================================================

class VideoDetailResponse(BaseModel):
    """
    Detailed video information response.

    Includes video metadata, processing status, and related entities.
    """
    id: UUID
    mall_id: UUID
    pin_id: UUID
    pin_name: Optional[str] = None

    # File information
    original_filename: str
    original_path: str
    file_size_bytes: int
    checksum_sha256: Optional[str] = None

    # Proxy and thumbnail
    proxy_path: Optional[str] = None
    proxy_size_bytes: Optional[int] = None
    thumbnail_path: Optional[str] = None

    # Video metadata
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    duration_seconds: Optional[float] = None
    codec: Optional[str] = None

    # Processing status
    processing_status: str = Field(
        ...,
        pattern="^(pending|processing|completed|failed)$",
        description="Processing status"
    )
    processing_job_id: Optional[UUID] = None
    processing_error: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None

    # Timestamps
    uploaded_at: datetime
    recorded_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Notes
    operator_notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class VideoListItem(BaseModel):
    """
    Compact video information for list responses.
    """
    id: UUID
    mall_id: UUID
    pin_id: UUID
    pin_name: Optional[str] = None

    original_filename: str
    file_size_bytes: int
    duration_seconds: Optional[float] = None

    # Processing status
    processing_status: str
    has_proxy: bool = Field(default=False, description="Whether proxy video exists")
    has_thumbnail: bool = Field(default=False, description="Whether thumbnail exists")

    uploaded_at: datetime
    recorded_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class VideoListResponse(BaseModel):
    """
    Paginated list of videos.
    """
    videos: List[VideoListItem]
    total: int = Field(..., description="Total number of videos matching filters")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, le=100, description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")


class VideoStreamUrlResponse(BaseModel):
    """
    Response with presigned URL for video streaming.
    """
    video_id: UUID
    url: str = Field(..., description="Presigned URL for streaming")
    expires_at: datetime = Field(..., description="When the URL expires")
    content_type: str = Field(default="video/mp4")
    file_size_bytes: Optional[int] = None
    duration_seconds: Optional[float] = None


class VideoDeleteResponse(BaseModel):
    """
    Response after deleting a video.
    """
    video_id: UUID
    deleted: bool = Field(default=True)
    files_deleted: List[str] = Field(
        default_factory=list,
        description="List of file paths deleted from storage"
    )
    message: str = Field(default="Video deleted successfully")
