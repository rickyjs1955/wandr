"""
Admin API endpoints for system monitoring and maintenance.

Provides endpoints for:
- Manual stuck job cleanup
- System statistics
- Job monitoring
- Health checks
"""
import logging
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case

from app.core.database import get_db
from app.models import ProcessingJob, Video, CameraPin
from app.services.video_service import get_video_service
from app.tasks.maintenance_tasks import cleanup_old_jobs, check_stuck_jobs, get_queue_stats
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# ============================================================================
# Response Schemas
# ============================================================================

class CleanupStuckJobsResponse(BaseModel):
    """Response for manual stuck job cleanup."""
    status: str = "completed"
    stuck_count: int = Field(..., description="Number of stuck jobs found and cleaned")
    stuck_job_ids: List[str] = Field(..., description="IDs of stuck jobs")
    cutoff_time: str = Field(..., description="ISO datetime used as cutoff")
    cleaned_at: datetime = Field(..., description="When cleanup was performed")


class CleanupOldJobsResponse(BaseModel):
    """Response for old job cleanup."""
    status: str = "completed"
    deleted_count: int = Field(..., description="Number of jobs deleted")
    cutoff_date: str = Field(..., description="ISO date used as cutoff")
    cleaned_at: datetime = Field(..., description="When cleanup was performed")


class SystemStatsResponse(BaseModel):
    """System-wide statistics."""
    videos: Dict[str, Any] = Field(..., description="Video statistics")
    jobs: Dict[str, Any] = Field(..., description="Job statistics")
    storage: Dict[str, Any] = Field(..., description="Storage statistics")
    timestamp: datetime


class JobListItem(BaseModel):
    """Job information for list view."""
    id: UUID
    video_id: UUID
    job_type: str
    status: str
    celery_task_id: Optional[str] = None
    queued_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None


class JobListResponse(BaseModel):
    """Paginated list of jobs."""
    jobs: List[JobListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class QueueStatsResponse(BaseModel):
    """Celery queue statistics."""
    status: str
    stats: Dict[str, Any] = Field(..., description="Queue statistics by status and type")
    retrieved_at: datetime


# ============================================================================
# Admin Endpoints
# ============================================================================

@router.post(
    "/cleanup-stuck-jobs",
    response_model=CleanupStuckJobsResponse,
    status_code=status.HTTP_200_OK,
    summary="Manually trigger stuck job cleanup",
    description="Find and mark stuck jobs as failed (admin only)",
)
def cleanup_stuck_jobs_endpoint(
    stuck_threshold_minutes: int = Query(120, ge=30, le=1440, description="Minutes before job considered stuck"),
    db: Session = Depends(get_db),
) -> CleanupStuckJobsResponse:
    """
    Manually trigger stuck job cleanup.

    This endpoint allows administrators to manually run the stuck job watchdog
    instead of waiting for the scheduled Celery Beat task.

    Query parameters:
    - stuck_threshold_minutes: Consider job stuck after N minutes (default: 120, max: 1440/24h)

    Returns:
    - Number of stuck jobs found and cleaned
    - List of stuck job IDs
    - Cutoff time used

    Note: Normally runs automatically every 15 minutes via Celery Beat.
    """
    try:
        logger.info(f"Manual stuck job cleanup triggered (threshold: {stuck_threshold_minutes} min)")

        # Call the Celery task synchronously
        result = check_stuck_jobs.apply(kwargs={"stuck_threshold_minutes": stuck_threshold_minutes}).get()

        return CleanupStuckJobsResponse(
            status=result["status"],
            stuck_count=result["stuck_count"],
            stuck_job_ids=result["stuck_job_ids"],
            cutoff_time=result["cutoff_time"],
            cleaned_at=datetime.utcnow(),
        )

    except Exception as e:
        logger.error(f"Failed to cleanup stuck jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup stuck jobs: {str(e)}",
        )


@router.post(
    "/cleanup-old-jobs",
    response_model=CleanupOldJobsResponse,
    status_code=status.HTTP_200_OK,
    summary="Manually trigger old job cleanup",
    description="Delete completed/failed jobs older than specified days (admin only)",
)
def cleanup_old_jobs_endpoint(
    days_to_keep: int = Query(30, ge=1, le=365, description="Keep jobs from last N days"),
    db: Session = Depends(get_db),
) -> CleanupOldJobsResponse:
    """
    Manually trigger old job cleanup.

    Deletes completed and failed processing jobs older than specified days.
    Helps manage database size and improve query performance.

    Query parameters:
    - days_to_keep: Keep jobs from last N days (default: 30, max: 365)

    Returns:
    - Number of jobs deleted
    - Cutoff date used

    Note: Normally runs automatically daily at 2 AM via Celery Beat.
    """
    try:
        logger.info(f"Manual old job cleanup triggered (days_to_keep: {days_to_keep})")

        # Call the Celery task synchronously
        result = cleanup_old_jobs.apply(kwargs={"days_to_keep": days_to_keep}).get()

        return CleanupOldJobsResponse(
            status=result["status"],
            deleted_count=result["deleted_count"],
            cutoff_date=result["cutoff_date"],
            cleaned_at=datetime.utcnow(),
        )

    except Exception as e:
        logger.error(f"Failed to cleanup old jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup old jobs: {str(e)}",
        )


@router.get(
    "/stats",
    response_model=SystemStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get system statistics",
    description="Get comprehensive system statistics (admin only)",
)
def get_system_stats(
    mall_id: Optional[UUID] = Query(None, description="Filter by mall ID"),
    db: Session = Depends(get_db),
) -> SystemStatsResponse:
    """
    Get system-wide statistics.

    Query parameters:
    - mall_id: Filter statistics by mall (optional)

    Returns:
    - Video statistics (total, by status, storage, duration)
    - Job statistics (total, by status, by type)
    - Storage statistics (total bytes, proxy bytes)
    """
    try:
        video_service = get_video_service(db)

        # Get video statistics
        video_stats = video_service.get_video_stats(mall_id=mall_id)

        # Get job statistics
        job_query = db.query(ProcessingJob)
        if mall_id:
            job_query = job_query.join(Video).join(CameraPin).filter(CameraPin.mall_id == mall_id)

        total_jobs = job_query.count()

        # Count by status
        job_status_counts = {}
        for status_name in ["pending", "running", "completed", "failed"]:
            count = job_query.filter(ProcessingJob.status == status_name).count()
            job_status_counts[status_name] = count

        # Count by type
        job_type_counts = {}
        for job_type in ["proxy_generation", "metadata_extraction", "thumbnail_generation"]:
            count = job_query.filter(ProcessingJob.job_type == job_type).count()
            job_type_counts[job_type] = count

        # Calculate average processing time for completed jobs
        completed_jobs = job_query.filter(
            and_(
                ProcessingJob.status == "completed",
                ProcessingJob.started_at.isnot(None),
                ProcessingJob.completed_at.isnot(None),
            )
        ).all()

        total_duration_seconds = 0
        for job in completed_jobs:
            if job.started_at and job.completed_at:
                duration = (job.completed_at - job.started_at).total_seconds()
                total_duration_seconds += duration

        avg_processing_time_seconds = (
            total_duration_seconds / len(completed_jobs) if completed_jobs else 0
        )

        # Storage statistics
        video_query = db.query(Video)
        if mall_id:
            video_query = video_query.join(CameraPin).filter(CameraPin.mall_id == mall_id)

        storage_stats = video_query.with_entities(
            func.sum(Video.file_size_bytes).label("total_bytes"),
            func.sum(case((Video.proxy_path != None, 1), else_=0)).label("proxy_count"),
        ).first()

        total_storage_bytes = int(storage_stats.total_bytes or 0)
        proxy_count = int(storage_stats.proxy_count or 0)

        return SystemStatsResponse(
            videos={
                "total": video_stats["total_videos"],
                "by_status": video_stats["by_status"],
                "total_storage_bytes": video_stats["total_storage_bytes"],
                "total_duration_seconds": video_stats["total_duration_seconds"],
            },
            jobs={
                "total": total_jobs,
                "by_status": job_status_counts,
                "by_type": job_type_counts,
                "avg_processing_time_seconds": avg_processing_time_seconds,
            },
            storage={
                "total_bytes": total_storage_bytes,
                "proxy_count": proxy_count,
                "total_gb": round(total_storage_bytes / (1024 ** 3), 2),
            },
            timestamp=datetime.utcnow(),
        )

    except Exception as e:
        logger.error(f"Failed to get system stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system stats: {str(e)}",
        )


@router.get(
    "/jobs",
    response_model=JobListResponse,
    status_code=status.HTTP_200_OK,
    summary="List processing jobs",
    description="Get paginated list of processing jobs with filters (admin only)",
)
def list_jobs(
    mall_id: Optional[UUID] = Query(None, description="Filter by mall ID"),
    status_filter: Optional[str] = Query(
        None,
        pattern="^(pending|running|completed|failed)$",
        description="Filter by job status"
    ),
    job_type: Optional[str] = Query(
        None,
        pattern="^(proxy_generation|metadata_extraction|thumbnail_generation)$",
        description="Filter by job type"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
) -> JobListResponse:
    """
    List processing jobs with filters and pagination.

    Query parameters:
    - mall_id: Filter by mall
    - status_filter: Filter by status (pending, running, completed, failed)
    - job_type: Filter by job type
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)

    Returns:
    - Paginated list of jobs with details
    """
    try:
        # Build query
        query = db.query(ProcessingJob)

        if mall_id:
            query = query.join(Video).join(CameraPin).filter(CameraPin.mall_id == mall_id)

        if status_filter:
            query = query.filter(ProcessingJob.status == status_filter)

        if job_type:
            query = query.filter(ProcessingJob.job_type == job_type)

        # Get total count
        total = query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        jobs = query.order_by(ProcessingJob.queued_at.desc()).offset(offset).limit(page_size).all()

        # Calculate total pages
        total_pages = (total + page_size - 1) // page_size

        # Convert to list items
        job_items = []
        for job in jobs:
            # Calculate duration if job completed
            duration_seconds = None
            if job.started_at and job.completed_at:
                duration_seconds = (job.completed_at - job.started_at).total_seconds()

            item = JobListItem(
                id=job.id,
                video_id=job.video_id,
                job_type=job.job_type,
                status=job.status,
                celery_task_id=job.celery_task_id,
                queued_at=job.queued_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                duration_seconds=duration_seconds,
                error_message=job.error_message,
            )
            job_items.append(item)

        return JobListResponse(
            jobs=job_items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list jobs: {str(e)}",
        )


@router.get(
    "/queue-stats",
    response_model=QueueStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Celery queue statistics",
    description="Get real-time Celery queue statistics (admin only)",
)
def get_celery_queue_stats(
    db: Session = Depends(get_db),
) -> QueueStatsResponse:
    """
    Get Celery queue statistics.

    Returns:
    - Job counts by status and type
    - Queue health metrics
    """
    try:
        # Call the Celery task synchronously
        result = get_queue_stats.apply().get()

        return QueueStatsResponse(
            status=result["status"],
            stats=result["stats"],
            retrieved_at=datetime.utcnow(),
        )

    except Exception as e:
        logger.error(f"Failed to get queue stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get queue stats: {str(e)}",
        )
