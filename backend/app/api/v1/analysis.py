"""
Computer Vision Analysis API endpoints.

Handles CV analysis operations:
- POST /analysis/videos/{video_id}:run - Trigger person detection
- GET /analysis/jobs/{job_id} - Get job status
- GET /analysis/videos/{video_id}/detections - Get detection results
- GET /analysis/videos/{video_id}/tracklets - Get tracklets (Phase 3.4+)
"""
import logging
from typing import Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.models import Video, ProcessingJob
from app.services.job_service import get_job_service, JobService
from app.services.storage_service import get_storage_service
from app.tasks.analysis_tasks import detect_persons_in_video
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["cv-analysis"])


# ============================================================================
# Request/Response Schemas
# ============================================================================

class RunAnalysisRequest(BaseModel):
    """Request schema for triggering CV analysis."""
    device: str = Field(
        default="cpu",
        pattern="^(cpu|cuda|mps)$",
        description="Device for inference: cpu, cuda (NVIDIA GPU), or mps (Apple Metal)"
    )
    conf_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Confidence threshold for person detection (0.0-1.0)"
    )
    analysis_fps: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Frame extraction rate for analysis (fps)"
    )


class RunAnalysisResponse(BaseModel):
    """Response schema for CV analysis trigger."""
    status: str = "queued"
    job_id: UUID = Field(..., description="Processing job ID for tracking")
    video_id: UUID
    message: str = "CV analysis job queued successfully"
    job_type: str = "cv_analysis"
    estimated_duration_minutes: Optional[float] = Field(
        None,
        description="Estimated processing time based on video duration"
    )


class JobStatusResponse(BaseModel):
    """Response schema for job status query."""
    job_id: UUID
    video_id: UUID
    job_type: str
    status: str = Field(
        ...,
        description="Job status: pending, running, completed, failed"
    )
    progress_percent: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Progress percentage (0-100)"
    )
    celery_task_id: Optional[str] = None
    queued_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Job results (available when status=completed)"
    )


class DetectionStatistics(BaseModel):
    """Statistics from person detection."""
    total_frames: int
    frames_with_people: int
    total_detections: int
    avg_people_per_frame: float


class DetectionResultsResponse(BaseModel):
    """Response schema for detection results."""
    video_id: UUID
    job_id: UUID
    status: str = "completed"
    analysis_params: Dict[str, Any]
    statistics: DetectionStatistics
    detections_path: str = Field(
        ...,
        description="S3 path to full detection results JSON"
    )
    message: str = "Detection results available"


# ============================================================================
# Analysis Endpoints
# ============================================================================

@router.post(
    "/videos/{video_id}:run",
    response_model=RunAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger person detection on video",
    description="""
    Trigger computer vision analysis on a video (Phase 3.1: Person Detection).

    This endpoint:
    1. Validates that the video exists and is ready for processing
    2. Creates a CV analysis processing job
    3. Queues the job to the 'cv_analysis' Celery queue
    4. Returns job_id for tracking progress

    The analysis pipeline (Phase 3.1):
    - Extracts frames at specified fps (default 1 fps)
    - Runs YOLOv8n person detection on each frame
    - Stores detection results as JSON in S3
    - Updates video.cv_processed flag

    Future phases will extend this to include:
    - Phase 3.2: Garment classification
    - Phase 3.3: Visual embedding extraction
    - Phase 3.4: Within-camera tracking (tracklet generation)

    Query the job status using GET /analysis/jobs/{job_id}
    Retrieve results using GET /analysis/videos/{video_id}/detections
    """,
)
def run_video_analysis(
    video_id: UUID = Path(..., description="Video UUID"),
    request: RunAnalysisRequest = RunAnalysisRequest(),
    db: Session = Depends(get_db),
    job_service: JobService = Depends(get_job_service),
) -> RunAnalysisResponse:
    """
    Trigger CV analysis on a video.

    Args:
        video_id: Video UUID to analyze
        request: Analysis parameters (device, confidence, fps)
        db: Database session
        job_service: Job service for creating processing jobs

    Returns:
        RunAnalysisResponse with job_id for tracking

    Raises:
        404: Video not found
        400: Video not ready for analysis (still uploading or already processing)
        500: Failed to queue analysis job
    """
    logger.info(f"CV analysis requested: video_id={video_id}, device={request.device}")

    # 1. Validate video exists
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video {video_id} not found"
        )

    # 2. Check video is ready for analysis
    if video.processing_status == "uploading":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Video is still uploading. Please wait for upload to complete."
        )

    if video.processing_status == "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Video processing failed. Cannot run CV analysis on failed video."
        )

    # 3. Check if video proxy generation is complete
    # CV analysis should run on proxy video (480p) for efficiency
    if not video.proxy_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Video proxy not generated yet. Please wait for proxy generation to complete."
        )

    # 4. Check if CV analysis already in progress
    existing_job = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.video_id == video_id)
        .filter(ProcessingJob.job_type == "cv_analysis")
        .filter(ProcessingJob.status.in_(["pending", "running"]))
        .first()
    )

    if existing_job:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"CV analysis already in progress for this video (job_id={existing_job.id})"
        )

    # 5. Create processing job
    try:
        job = job_service.create_job(
            video_id=video_id,
            job_type="cv_analysis",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # 6. Queue Celery task
    try:
        task = detect_persons_in_video.apply_async(
            kwargs={
                "video_id": str(video_id),
                "job_id": str(job.id),
                "device": request.device,
                "conf_threshold": request.conf_threshold,
                "analysis_fps": request.analysis_fps,
            },
            queue="cv_analysis",
            priority=7,  # Higher priority than proxy generation
        )

        # Update job with celery task ID
        job.celery_task_id = task.id
        db.commit()

        logger.info(
            f"✅ CV analysis queued: video_id={video_id}, job_id={job.id}, "
            f"task_id={task.id}, device={request.device}"
        )

    except Exception as e:
        logger.error(f"Failed to queue CV analysis: {e}")
        # Update job status to failed
        job.status = "failed"
        job.error_message = f"Failed to queue task: {str(e)}"
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue CV analysis: {str(e)}"
        )

    # 7. Estimate processing time (rough estimate: 1 second per frame)
    estimated_duration = None
    if video.duration_seconds:
        # analysis_fps frames per second of video
        estimated_frames = video.duration_seconds * request.analysis_fps
        # Assume ~0.5 seconds processing per frame (YOLOv8n on CPU)
        estimated_duration = round((estimated_frames * 0.5) / 60, 1)  # Convert to minutes

    return RunAnalysisResponse(
        status="queued",
        job_id=job.id,
        video_id=video_id,
        message="CV analysis job queued successfully",
        job_type="cv_analysis",
        estimated_duration_minutes=estimated_duration,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get CV analysis job status",
    description="""
    Query the status of a CV analysis job.

    Returns:
    - Job status: pending, running, completed, failed
    - Progress percentage (if available)
    - Result data (if completed)
    - Error message (if failed)

    Poll this endpoint to track job progress.
    Typical polling interval: 2-5 seconds.
    """,
)
def get_job_status(
    job_id: UUID = Path(..., description="Processing job UUID"),
    db: Session = Depends(get_db),
) -> JobStatusResponse:
    """
    Get status of a CV analysis job.

    Args:
        job_id: Job UUID
        db: Database session

    Returns:
        JobStatusResponse with current status and results

    Raises:
        404: Job not found
    """
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )

    # Calculate duration if job has started
    duration_seconds = None
    if job.started_at and job.completed_at:
        duration_seconds = (job.completed_at - job.started_at).total_seconds()

    return JobStatusResponse(
        job_id=job.id,
        video_id=job.video_id,
        job_type=job.job_type,
        status=job.status,
        progress_percent=job.progress_percent,
        celery_task_id=job.celery_task_id,
        queued_at=job.queued_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        duration_seconds=duration_seconds,
        error_message=job.error_message,
        result_data=job.result_data,
    )


@router.get(
    "/videos/{video_id}/detections",
    response_model=DetectionResultsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get person detection results",
    description="""
    Retrieve person detection results for a video.

    Returns summary statistics and a presigned URL to download the full
    detection results JSON file from S3.

    The detection results JSON contains:
    - Frame-by-frame detection data
    - Bounding boxes for each detected person
    - Confidence scores
    - Frame timestamps

    Requires that CV analysis has completed successfully.
    """,
)
def get_detection_results(
    video_id: UUID = Path(..., description="Video UUID"),
    db: Session = Depends(get_db),
) -> DetectionResultsResponse:
    """
    Get person detection results for a video.

    Args:
        video_id: Video UUID
        db: Database session

    Returns:
        DetectionResultsResponse with statistics and S3 path

    Raises:
        404: Video not found or no detection results available
        400: CV analysis not completed yet
    """
    # 1. Check video exists
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video {video_id} not found"
        )

    # 2. Check CV analysis completed
    if not video.cv_processed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CV analysis not completed for this video. Run analysis first using POST /analysis/videos/{video_id}:run"
        )

    # 3. Find completed CV analysis job
    job = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.video_id == video_id)
        .filter(ProcessingJob.job_type == "cv_analysis")
        .filter(ProcessingJob.status == "completed")
        .order_by(ProcessingJob.completed_at.desc())
        .first()
    )

    if not job or not job.result_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No detection results found for this video"
        )

    # 4. Extract result data
    result = job.result_data
    detection_results_path = result.get("detection_results_path")
    statistics = result.get("statistics", {})

    if not detection_results_path:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Detection results path missing from job data"
        )

    # 5. Return response with S3 path
    # Client can use GET /videos/{video_id}/stream/detections to get presigned URL
    return DetectionResultsResponse(
        video_id=video_id,
        job_id=job.id,
        status="completed",
        analysis_params={
            "model": "yolov8n",
            "device": "cpu",  # Would need to store this in job params
            "conf_threshold": 0.7,
            "analysis_fps": 1.0,
        },
        statistics=DetectionStatistics(**statistics),
        detections_path=detection_results_path,
        message="Detection results available",
    )


@router.get(
    "/videos/{video_id}/tracklets",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="Get tracklets for video (Phase 3.4+)",
    description="""
    Get within-camera tracklets for a video.

    **Status**: Not implemented yet (Phase 3.4)

    This endpoint will return tracklet data once Phase 3.4
    (within-camera tracking with ByteTrack) is completed.

    A tracklet represents a single person tracked within one camera view,
    including:
    - Track ID (camera-local)
    - Time in/out timestamps
    - Outfit descriptor (type, color, visual embedding)
    - Bounding box statistics
    - Quality score
    """,
)
def get_video_tracklets(
    video_id: UUID = Path(..., description="Video UUID"),
    db: Session = Depends(get_db),
):
    """
    Get tracklets for a video (Phase 3.4+).

    Not implemented yet - will be available in Phase 3.4
    when within-camera tracking is complete.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Tracklet extraction not implemented yet (Phase 3.4)"
    )
