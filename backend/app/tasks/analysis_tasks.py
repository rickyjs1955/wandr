"""
Computer Vision Analysis Tasks

Celery tasks for CV operations:
- Person detection (Phase 3.1)
- Garment classification (Phase 3.2)
- Visual embedding extraction (Phase 3.3)
- Within-camera tracking (Phase 3.4)
- Cross-camera re-identification (Phase 4)
"""
import logging
import os
import tempfile
from uuid import UUID
from typing import Dict, Any, List
from pathlib import Path
import json

from celery import Task
from sqlalchemy.orm import Session
from sqlalchemy import func
import numpy as np
import cv2

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models import Video, ProcessingJob
from app.services.storage_service import get_storage_service
from app.services.ffmpeg_service import get_ffmpeg_service
from app.cv.person_detector import create_detector

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Base task with database session management."""

    _db: Session = None

    @property
    def db(self) -> Session:
        """Get database session."""
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        """Close database session after task completion."""
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="app.tasks.analysis_tasks.detect_persons_in_video",
    max_retries=2,
    default_retry_delay=300,  # 5 minutes
)
def detect_persons_in_video(
    self,
    video_id: str,
    job_id: str,
    device: str = "cpu",
    conf_threshold: float = 0.7,
    analysis_fps: float = 1.0,
) -> Dict[str, Any]:
    """
    Detect people in video frames at 1 fps (Phase 3.1).

    This task:
    1. Downloads video from S3
    2. Extracts frames at analysis_fps (default 1 fps)
    3. Runs YOLOv8n person detection on each frame
    4. Stores detection results as JSON
    5. Updates job status with progress

    In Phase 3.4, this will be extended to include within-camera tracking
    and tracklet generation.

    Args:
        video_id: Video UUID (as string)
        job_id: ProcessingJob UUID (as string)
        device: Device for inference ('cpu', 'cuda', 'mps')
        conf_threshold: Confidence threshold for detections (0.0-1.0)
        analysis_fps: Frame extraction rate for analysis (default 1.0)

    Returns:
        Dict with detection results and statistics

    Raises:
        Exception: On detection or storage errors (triggers retry)
    """
    video_uuid = UUID(video_id)
    job_uuid = UUID(job_id)

    logger.info(
        f"Starting person detection: video_id={video_id}, job_id={job_id}, "
        f"device={device}, conf={conf_threshold}, fps={analysis_fps}"
    )

    try:
        # Get video and job records
        video = self.db.query(Video).filter(Video.id == video_uuid).first()
        if not video:
            raise ValueError(f"Video {video_id} not found")

        job = self.db.query(ProcessingJob).filter(ProcessingJob.id == job_uuid).first()
        if not job:
            raise ValueError(f"ProcessingJob {job_id} not found")

        # Update job status
        job.status = "running"
        job.started_at = func.now()
        job.celery_task_id = self.request.id
        job.progress_percent = 0
        self.db.commit()

        # Get services
        storage = get_storage_service()
        ffmpeg = get_ffmpeg_service()

        # Create temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)

            # 1. Download video from S3
            logger.info(f"Downloading video from S3: {video.original_path}")
            video_local_path = temp_dir_path / f"video_{video.id}.mp4"
            storage.download_file(video.original_path, str(video_local_path))

            # Update progress
            job.progress_percent = 10
            self.db.commit()

            # 2. Extract frames at analysis_fps
            logger.info(f"Extracting frames at {analysis_fps} fps")
            frames_dir = temp_dir_path / "frames"
            frames_dir.mkdir(exist_ok=True)

            frame_paths = ffmpeg.extract_frames(
                input_path=str(video_local_path),
                output_dir=str(frames_dir),
                fps=analysis_fps,
                quality=2,  # High quality for CV analysis
            )

            total_frames = len(frame_paths)
            logger.info(f"Extracted {total_frames} frames for analysis")

            # Update progress
            job.progress_percent = 30
            self.db.commit()

            # 3. Initialize person detector
            logger.info(f"Initializing PersonDetector on device: {device}")
            detector = create_detector(
                model_name="yolov8n.pt",
                device=device,
                conf_threshold=conf_threshold,
            )

            # 4. Run detection on each frame
            logger.info("Running person detection on frames")
            all_detections = []
            frames_with_people = 0
            total_people_detected = 0

            for i, frame_path in enumerate(frame_paths):
                # Read frame
                frame = cv2.imread(frame_path)
                if frame is None:
                    logger.warning(f"Failed to read frame: {frame_path}")
                    continue

                # Convert BGR to RGB (YOLOv8 expects RGB)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Run detection
                detections = detector.detect(frame_rgb)

                # Store detections with frame metadata
                frame_number = i + 1
                frame_timestamp = i / analysis_fps  # Timestamp from 0 (first frame at t=0)

                frame_result = {
                    "frame_number": frame_number,
                    "timestamp_seconds": round(frame_timestamp, 2),
                    "detections": detections,
                    "person_count": len(detections),
                }
                all_detections.append(frame_result)

                # Update statistics
                if len(detections) > 0:
                    frames_with_people += 1
                    total_people_detected += len(detections)

                # Update progress periodically (every 10 frames)
                if i % 10 == 0:
                    progress = 30 + int((i / total_frames) * 60)  # 30% to 90%
                    job.progress_percent = progress
                    self.db.commit()
                    logger.info(
                        f"Detection progress: {i}/{total_frames} frames "
                        f"({progress}%)"
                    )

            # Update progress
            job.progress_percent = 90
            self.db.commit()

            # 5. Save detection results to S3
            logger.info("Saving detection results to S3")

            # Prepare results JSON
            detection_results = {
                "video_id": str(video.id),
                "job_id": str(job.id),
                "analysis_params": {
                    "model": "yolov8n",
                    "device": device,
                    "conf_threshold": conf_threshold,
                    "analysis_fps": analysis_fps,
                },
                "statistics": {
                    "total_frames": total_frames,
                    "frames_with_people": frames_with_people,
                    "total_detections": total_people_detected,
                    "avg_people_per_frame": round(
                        total_people_detected / total_frames, 2
                    ) if total_frames > 0 else 0,
                },
                "detections": all_detections,
            }

            # Save to local file
            results_local_path = temp_dir_path / f"detections_{video.id}.json"
            with open(results_local_path, "w") as f:
                json.dump(detection_results, f, indent=2)

            # Upload to S3
            results_s3_path = f"cv_results/{video.mall_id}/{video.id}/detections.json"
            storage.upload_file(
                str(results_local_path),
                results_s3_path,
                content_type="application/json",
            )

            logger.info(f"Detection results saved to S3: {results_s3_path}")

        # 6. Update video record with CV processing status
        video.cv_processed = True
        # Note: tracklet_count will be set in Phase 3.4 when tracking is implemented
        video.cv_job_id = job_uuid
        self.db.commit()

        # 7. Update job status
        job.status = "completed"
        job.completed_at = func.now()
        job.progress_percent = 100
        job.result_data = {
            "status": "success",
            "detection_results_path": results_s3_path,
            "statistics": detection_results["statistics"],
        }
        self.db.commit()

        logger.info(
            f"✅ Person detection completed: video_id={video_id}, "
            f"frames={total_frames}, detections={total_people_detected}"
        )

        return {
            "status": "completed",
            "video_id": str(video.id),
            "job_id": str(job.id),
            "detection_results_path": results_s3_path,
            "statistics": detection_results["statistics"],
        }

    except Exception as e:
        logger.error(f"❌ Person detection failed: video_id={video_id}, error={e}")

        # Update video cv_processed to False
        video = self.db.query(Video).filter(Video.id == video_uuid).first()
        if video:
            video.cv_processed = False

        # Update job status to failed
        job = self.db.query(ProcessingJob).filter(ProcessingJob.id == job_uuid).first()
        if job:
            job.status = "failed"
            job.completed_at = func.now()
            job.error_message = str(e)
            self.db.commit()

        # Retry on transient errors
        if self.request.retries < self.max_retries:
            logger.info(
                f"Retrying person detection "
                f"(attempt {self.request.retries + 1}/{self.max_retries})"
            )
            raise self.retry(exc=e)

        # Give up after max retries
        raise


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="app.tasks.analysis_tasks.run_full_cv_pipeline",
    max_retries=2,
)
def run_full_cv_pipeline(
    self,
    video_id: str,
    job_id: str,
    device: str = "cpu",
) -> Dict[str, Any]:
    """
    Run full CV pipeline on video (Phase 3 complete).

    This is a placeholder for the complete pipeline that will be implemented
    across Phase 3 sub-phases:

    Phase 3.1 (Current): Person detection only
    Phase 3.2: + Garment classification
    Phase 3.3: + Visual embedding extraction
    Phase 3.4: + Within-camera tracking (tracklet generation)

    For now, this just calls detect_persons_in_video.

    Args:
        video_id: Video UUID (as string)
        job_id: ProcessingJob UUID (as string)
        device: Device for inference ('cpu', 'cuda', 'mps')

    Returns:
        Dict with pipeline results
    """
    logger.info(f"Running full CV pipeline: video_id={video_id}, job_id={job_id}")

    # For Phase 3.1, just run person detection
    # This will be extended in subsequent phases
    result = detect_persons_in_video(
        video_id=video_id,
        job_id=job_id,
        device=device,
    )

    return result
