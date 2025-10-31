"""
Video upload API endpoints.

Handles multipart video uploads:
- POST /videos/upload/initiate - Start upload session
- POST /videos/upload/{upload_id}/part-url - Get presigned URL for part
- POST /videos/upload/{upload_id}/complete - Finalize upload
- POST /videos/upload/{upload_id}/abort - Cancel upload
- GET /videos/upload/{upload_id}/status - Check upload status
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.upload_service import get_upload_service, UploadService
from app.services.job_service import get_job_service, JobService
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
)

router = APIRouter(prefix="/videos", tags=["videos"])


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
