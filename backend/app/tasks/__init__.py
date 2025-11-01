"""
Background tasks package.

Celery tasks for:
- Video processing (proxy generation)
- CV analysis (person detection, re-identification)
- Maintenance (cleanup, monitoring)
"""
from app.tasks.video_tasks import generate_proxy_video
from app.tasks.maintenance_tasks import cleanup_old_jobs, check_stuck_jobs
from app.tasks.analysis_tasks import detect_persons_in_video, run_full_cv_pipeline

__all__ = [
    "generate_proxy_video",
    "cleanup_old_jobs",
    "check_stuck_jobs",
    "detect_persons_in_video",
    "run_full_cv_pipeline",
]
