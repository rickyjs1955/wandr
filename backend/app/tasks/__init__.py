"""
Background tasks package.

Celery tasks for:
- Video processing (proxy generation)
- CV analysis (person detection, re-identification)
- Maintenance (cleanup, monitoring)
"""
from app.tasks.video_tasks import generate_proxy_video
from app.tasks.maintenance_tasks import cleanup_old_jobs, check_stuck_jobs

__all__ = [
    "generate_proxy_video",
    "cleanup_old_jobs",
    "check_stuck_jobs",
]
