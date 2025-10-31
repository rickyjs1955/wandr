"""
Video upload and management API endpoints.

Handles multipart video uploads:
- POST /videos/upload/initiate - Start upload session
- POST /videos/upload/{upload_id}/part-url - Get presigned URL for part
- POST /videos/upload/{upload_id}/complete - Finalize upload
- POST /videos/upload/{upload_id}/abort - Cancel upload
- GET /videos/upload/{upload_id}/status - Check upload status

Handles video management (Phase 2.6):
- GET /videos - List videos with filters
- GET /videos/{video_id} - Get video details
- GET /videos/{video_id}/stream/{stream_type} - Get streaming URL
- GET /videos/{video_id}/thumbnail - Get thumbnail URL
- DELETE /videos/{video_id} - Delete video
"""
import logging
from typing import Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.upload_service import get_upload_service, UploadService
from app.services.job_service import get_job_service, JobService
from app.services.video_service import get_video_service, VideoService
from app.services.storage_service import get_storage_service
from app.models import ProcessingJob
from app.schemas import (
    MultipartUploadInitiateRequest,
    MultipartUploadInitiateResponse,
    MultipartUploadPartUrlRequest,
    MultipartUploadPartUrlResponse,
    MultipartUploadCompleteRequest,
    MultipartUploadCompleteResponse,
    MultipartUploadAbortRequest,
    MultipartUploadAbortResponse,
    MultipartUploadStatusResponse,
    VideoListResponse,
    VideoListItem,
    VideoDetailResponse,
    VideoStreamUrlResponse,
    VideoDeleteResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/videos", tags=["videos"])


# ============================================================================
# Helper Functions
# ============================================================================

def get_thumbnail_path_from_job(db: Session, video_id: UUID) -> Optional[str]:
    """
    Get thumbnail path from processing job result_data.

    Args:
        db: Database session
        video_id: Video UUID

    Returns:
        Thumbnail path or None if not available
    """
    job = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.video_id == video_id)
        .filter(ProcessingJob.job_type == "proxy_generation")
        .filter(ProcessingJob.status == "completed")
        .first()
    )

    if job and job.result_data:
        return job.result_data.get("thumbnail_path")
    return None


# ============================================================================
# Multipart Upload Endpoints
# ============================================================================

@router.post(
    "/upload/initiate",
    response_model=MultipartUploadInitiateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate multipart upload",
    description="""
    Start a multipart upload session for a large video file.

    This endpoint:
    1. Validates mall_id and pin_id exist
    2. Creates a video database record with status 'uploading'
    3. Initiates an S3 multipart upload session
    4. Returns upload_id and video_id for tracking

    The client should then:
    1. Split the video file into parts (5MB-5GB each, max 10000 parts)
    2. Request presigned URLs for each part using POST /upload/{upload_id}/part-url
    3. Upload each part directly to S3 using the presigned URLs
    4. Complete the upload using POST /upload/{upload_id}/complete

    Upload sessions expire after 4 hours.
    """,
)
def initiate_multipart_upload(
    request: MultipartUploadInitiateRequest,
    upload_service: UploadService = Depends(get_upload_service),
    # TODO: Add authentication dependency
    # current_user: User = Depends(get_current_user),
) -> MultipartUploadInitiateResponse:
    """Initiate a multipart upload session."""
    try:
        # Check for duplicate if checksum provided
        if request.checksum_sha256:
            duplicate = upload_service.check_duplicate(
                request.mall_id,
                request.pin_id,
                request.checksum_sha256,
            )
            if duplicate:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": "duplicate_video",
                        "message": "Video with this checksum already exists for this pin",
                        "existing_video_id": str(duplicate.id),
                    },
                )

        # Initiate upload
        upload_id, video_id, expires_at = upload_service.initiate_upload(
            mall_id=request.mall_id,
            pin_id=request.pin_id,
            filename=request.filename,
            file_size_bytes=request.file_size_bytes,
            content_type=request.content_type,
            checksum_sha256=request.checksum_sha256,
            recorded_at=request.recorded_at,
            operator_notes=request.operator_notes,
            # uploaded_by_user_id=current_user.id,  # TODO: Add when auth is ready
            video_width=request.video_width,
            video_height=request.video_height,
            video_fps=request.video_fps,
            video_duration_seconds=request.video_duration_seconds,
        )

        return MultipartUploadInitiateResponse(
            upload_id=upload_id,
            video_id=video_id,
            mall_id=request.mall_id,
            pin_id=request.pin_id,
            filename=request.filename,
            file_size_bytes=request.file_size_bytes,
            checksum_required=request.checksum_sha256 is not None,
            expires_at=expires_at,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate upload: {str(e)}",
        )


@router.post(
    "/upload/{upload_id}/part-url",
    response_model=MultipartUploadPartUrlResponse,
    status_code=status.HTTP_200_OK,
    summary="Get presigned URL for part upload",
    description="""
    Request a presigned URL for uploading a specific part of the video.

    The client should:
    1. Call this endpoint for each part (part_number 1, 2, 3, ...)
    2. Upload the part directly to the returned presigned_url using HTTP PUT
    3. Save the ETag returned by S3 (in the response headers)
    4. Provide all ETags when completing the upload

    Part upload example (JavaScript):
    ```javascript
    const response = await fetch(presigned_url, {
        method: 'PUT',
        body: partData,
        headers: {
            'Content-Type': 'video/mp4'
        }
    });
    const etag = response.headers.get('ETag');
    ```

    Presigned URLs expire after 1 hour.
    """,
)
def get_part_upload_url(
    upload_id: UUID,
    video_id: UUID,
    request: MultipartUploadPartUrlRequest,
    upload_service: UploadService = Depends(get_upload_service),
) -> MultipartUploadPartUrlResponse:
    """Get presigned URL for uploading a specific part."""
    try:
        presigned_url, expires_at = upload_service.generate_part_url(
            upload_id=upload_id,
            video_id=video_id,
            part_number=request.part_number,
        )

        return MultipartUploadPartUrlResponse(
            upload_id=upload_id,
            part_number=request.part_number,
            presigned_url=presigned_url,
            expires_at=expires_at,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate part URL: {str(e)}",
        )


@router.post(
    "/upload/{upload_id}/complete",
    response_model=MultipartUploadCompleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Complete multipart upload",
    description="""
    Finalize a multipart upload by providing all uploaded parts.

    This endpoint:
    1. Validates the checksum (if provided)
    2. Combines all parts into a single file in S3
    3. Updates the video database record to status 'uploaded'
    4. Optionally queues a background job for proxy generation

    The client must provide:
    - List of all parts with their part_number and etag
    - Optional final SHA256 checksum for validation

    After completion, the video is ready for processing.
    """,
)
def complete_multipart_upload(
    upload_id: UUID,
    video_id: UUID,
    request: MultipartUploadCompleteRequest,
    upload_service: UploadService = Depends(get_upload_service),
    job_service: JobService = Depends(get_job_service),
) -> MultipartUploadCompleteResponse:
    """Complete a multipart upload."""
    try:
        # Convert Pydantic models to dicts for storage service
        parts = [
            {
                "part_number": part.part_number,
                "etag": part.etag,
                "size_bytes": part.size_bytes,
            }
            for part in request.parts
        ]

        result = upload_service.complete_upload(
            upload_id=upload_id,
            video_id=video_id,
            parts=parts,
            final_checksum_sha256=request.final_checksum_sha256,
        )

        # Queue background job for proxy generation
        processing_job = job_service.queue_proxy_generation(
            video_id=video_id,
            priority=5,  # Default priority
        )

        return MultipartUploadCompleteResponse(
            video_id=result["video_id"],
            upload_id=upload_id,
            status="completed",
            object_path=result["object_path"],
            file_size_bytes=result["file_size_bytes"],
            checksum_sha256=result.get("checksum_sha256"),
            processing_job_id=processing_job.id,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete upload: {str(e)}",
        )


@router.post(
    "/upload/{upload_id}/abort",
    response_model=MultipartUploadAbortResponse,
    status_code=status.HTTP_200_OK,
    summary="Abort multipart upload",
    description="""
    Cancel a multipart upload and clean up partial files.

    This endpoint:
    1. Aborts the S3 multipart upload
    2. Cleans up any uploaded parts
    3. Updates the video database record to status 'aborted'

    Use this when:
    - Upload fails and cannot be retried
    - User cancels the upload
    - Upload session expires

    After aborting, the upload_id cannot be reused.
    To upload the same file again, initiate a new upload session.
    """,
)
def abort_multipart_upload(
    upload_id: UUID,
    video_id: UUID,
    request: MultipartUploadAbortRequest,
    upload_service: UploadService = Depends(get_upload_service),
) -> MultipartUploadAbortResponse:
    """Abort a multipart upload."""
    try:
        parts_cleaned_up = upload_service.abort_upload(
            upload_id=upload_id,
            video_id=video_id,
            reason=request.reason,
        )

        return MultipartUploadAbortResponse(
            upload_id=upload_id,
            video_id=video_id,
            status="aborted",
            parts_cleaned_up=parts_cleaned_up,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to abort upload: {str(e)}",
        )


@router.get(
    "/upload/{upload_id}/status",
    response_model=MultipartUploadStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get upload status",
    description="""
    Check the current status of a multipart upload session.

    Returns:
    - Upload status (uploading, completed, aborted, failed)
    - Progress information (bytes uploaded, parts count)
    - Timestamps (created, expires, completed)
    - Error message (if failed)

    Use this to:
    - Resume interrupted uploads
    - Check if upload is still valid (not expired)
    - Display upload progress to user
    """,
)
def get_upload_status(
    upload_id: UUID,
    video_id: UUID,
    upload_service: UploadService = Depends(get_upload_service),
) -> MultipartUploadStatusResponse:
    """Get status of a multipart upload."""
    try:
        status_data = upload_service.get_upload_status(
            upload_id=upload_id,
            video_id=video_id,
        )

        return MultipartUploadStatusResponse(**status_data)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get upload status: {str(e)}",
        )


# ============================================================================
# Video Management Endpoints (Phase 2.6)
# ============================================================================

@router.get(
    "",
    response_model=VideoListResponse,
    status_code=status.HTTP_200_OK,
    summary="List videos with filters",
    description="Get paginated list of videos with optional filters",
)
def list_videos(
    mall_id: Optional[UUID] = Query(None, description="Filter by mall ID"),
    pin_id: Optional[UUID] = Query(None, description="Filter by camera pin ID"),
    processing_status: Optional[str] = Query(
        None,
        pattern="^(pending|processing|completed|failed)$",
        description="Filter by processing status"
    ),
    has_proxy: Optional[bool] = Query(None, description="Filter by proxy existence"),
    uploaded_after: Optional[datetime] = Query(None, description="Filter videos uploaded after"),
    uploaded_before: Optional[datetime] = Query(None, description="Filter videos uploaded before"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
) -> VideoListResponse:
    """
    List videos with filters and pagination.

    Query parameters:
    - mall_id: Filter by mall
    - pin_id: Filter by camera pin
    - processing_status: Filter by status (pending, processing, completed, failed)
    - has_proxy: Filter by proxy existence (true/false)
    - uploaded_after: ISO datetime
    - uploaded_before: ISO datetime
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)

    Returns:
    - Paginated list of videos with metadata
    """
    try:
        video_service = get_video_service(db)

        videos, total = video_service.list_videos(
            mall_id=mall_id,
            pin_id=pin_id,
            processing_status=processing_status,
            has_proxy=has_proxy,
            uploaded_after=uploaded_after,
            uploaded_before=uploaded_before,
            page=page,
            page_size=page_size,
        )

        # Calculate total pages
        total_pages = (total + page_size - 1) // page_size

        # Convert to list items
        video_items = []
        for video in videos:
            # Check if thumbnail exists via processing job result_data
            thumbnail_path = get_thumbnail_path_from_job(db, video.id)

            item = VideoListItem(
                id=video.id,
                mall_id=video.camera_pin.mall_id,
                pin_id=video.camera_pin_id,
                pin_name=video.camera_pin.name if video.camera_pin else None,
                original_filename=video.original_filename,
                file_size_bytes=video.file_size_bytes,
                duration_seconds=video.duration_seconds,
                processing_status=video.processing_status,
                has_proxy=video.proxy_path is not None,
                has_thumbnail=thumbnail_path is not None,
                uploaded_at=video.uploaded_at,
                recorded_at=video.recorded_at,
            )
            video_items.append(item)

        return VideoListResponse(
            videos=video_items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list videos: {str(e)}",
        )


@router.get(
    "/{video_id}",
    response_model=VideoDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get video details",
    description="Get detailed information about a specific video",
)
def get_video_details(
    video_id: UUID,
    db: Session = Depends(get_db),
) -> VideoDetailResponse:
    """
    Get detailed information about a video.

    Path parameters:
    - video_id: Video UUID

    Returns:
    - Complete video information including metadata, processing status, and file paths
    """
    try:
        video_service = get_video_service(db)
        video = video_service.get_video(video_id)

        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video {video_id} not found",
            )

        # Calculate proxy size if proxy exists
        proxy_size_bytes = None
        if video.proxy_path:
            try:
                storage = get_storage_service()
                metadata = storage.get_file_metadata(video.proxy_path)
                proxy_size_bytes = metadata.get("size")
            except Exception as e:
                logger.warning(f"Failed to get proxy file size: {e}")

        # Get thumbnail path from processing job result_data
        thumbnail_path = get_thumbnail_path_from_job(db, video.id)

        return VideoDetailResponse(
            id=video.id,
            mall_id=video.camera_pin.mall_id,
            pin_id=video.camera_pin_id,
            pin_name=video.camera_pin.name if video.camera_pin else None,
            original_filename=video.original_filename,
            original_path=video.original_path,
            file_size_bytes=video.file_size_bytes,
            checksum_sha256=video.checksum_sha256,
            proxy_path=video.proxy_path,
            proxy_size_bytes=proxy_size_bytes,
            thumbnail_path=thumbnail_path,
            width=video.width,
            height=video.height,
            fps=video.fps,
            duration_seconds=video.duration_seconds,
            codec=video.codec,
            processing_status=video.processing_status,
            processing_job_id=video.processing_job_id,
            processing_error=video.processing_error,
            processing_started_at=video.processing_started_at,
            processing_completed_at=video.processing_completed_at,
            uploaded_at=video.uploaded_at,
            recorded_at=video.recorded_at,
            created_at=video.created_at,
            updated_at=video.updated_at,
            operator_notes=video.operator_notes,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get video details: {str(e)}",
        )


@router.get(
    "/{video_id}/stream/{stream_type}",
    response_model=VideoStreamUrlResponse,
    status_code=status.HTTP_200_OK,
    summary="Get video stream URL",
    description="Generate presigned URL for video streaming (proxy or original)",
)
def get_video_stream_url(
    video_id: UUID,
    stream_type: str = Path(..., pattern="^(proxy|original)$", description="Stream type"),
    expires_minutes: int = Query(60, ge=5, le=1440, description="URL expiration in minutes"),
    db: Session = Depends(get_db),
) -> VideoStreamUrlResponse:
    """
    Generate presigned URL for video streaming.

    Path parameters:
    - video_id: Video UUID
    - stream_type: "proxy" (480p @ 10fps) or "original" (full quality)

    Query parameters:
    - expires_minutes: URL expiration time in minutes (default: 60, max: 1440/24h)

    Returns:
    - Presigned URL for streaming
    - URL expires after specified time
    """
    try:
        video_service = get_video_service(db)

        # Generate stream URL
        result = video_service.generate_stream_url(
            video_id=video_id,
            stream_type=stream_type,
            expires_minutes=expires_minutes,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video {video_id} not found",
            )

        presigned_url, expires_at = result

        # Get video details for response metadata
        video = video_service.get_video(video_id)

        # Determine file size based on stream type
        if stream_type == "proxy" and video.proxy_path:
            try:
                storage = get_storage_service()
                metadata = storage.get_file_metadata(video.proxy_path)
                file_size_bytes = metadata.get("size")
            except:
                file_size_bytes = None
        else:
            file_size_bytes = video.file_size_bytes

        return VideoStreamUrlResponse(
            video_id=video_id,
            url=presigned_url,
            expires_at=expires_at,
            content_type="video/mp4",
            file_size_bytes=file_size_bytes,
            duration_seconds=video.duration_seconds,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate stream URL: {str(e)}",
        )


@router.get(
    "/{video_id}/thumbnail",
    response_model=VideoStreamUrlResponse,
    status_code=status.HTTP_200_OK,
    summary="Get thumbnail URL",
    description="Generate presigned URL for video thumbnail",
)
def get_thumbnail_url(
    video_id: UUID,
    expires_minutes: int = Query(60, ge=5, le=1440, description="URL expiration in minutes"),
    db: Session = Depends(get_db),
) -> VideoStreamUrlResponse:
    """
    Generate presigned URL for video thumbnail.

    Path parameters:
    - video_id: Video UUID

    Query parameters:
    - expires_minutes: URL expiration time in minutes (default: 60, max: 1440/24h)

    Returns:
    - Presigned URL for thumbnail image (JPEG)
    """
    try:
        video_service = get_video_service(db)

        # Generate thumbnail URL
        result = video_service.generate_thumbnail_url(
            video_id=video_id,
            expires_minutes=expires_minutes,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video {video_id} not found",
            )

        presigned_url, expires_at = result

        return VideoStreamUrlResponse(
            video_id=video_id,
            url=presigned_url,
            expires_at=expires_at,
            content_type="image/jpeg",
            file_size_bytes=None,
            duration_seconds=None,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate thumbnail URL: {str(e)}",
        )


@router.delete(
    "/{video_id}",
    response_model=VideoDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete video",
    description="Delete video and all associated files from storage",
)
def delete_video(
    video_id: UUID,
    delete_files: bool = Query(True, description="Also delete files from storage"),
    db: Session = Depends(get_db),
) -> VideoDeleteResponse:
    """
    Delete video and optionally all associated files.

    Path parameters:
    - video_id: Video UUID

    Query parameters:
    - delete_files: If true, also delete files from S3/MinIO (default: true)

    Returns:
    - Confirmation and list of deleted files

    Note: This operation cannot be undone.
    """
    try:
        video_service = get_video_service(db)

        # Delete video
        success, deleted_files = video_service.delete_video(
            video_id=video_id,
            delete_from_storage=delete_files,
        )

        return VideoDeleteResponse(
            video_id=video_id,
            deleted=success,
            files_deleted=deleted_files,
            message=f"Video deleted successfully. {len(deleted_files)} file(s) removed from storage."
            if delete_files
            else "Video deleted from database only.",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete video: {str(e)}",
        )
