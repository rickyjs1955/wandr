"""
Camera pin and video models.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Integer, Float, Boolean, ARRAY, Text, ForeignKey, BigInteger, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import sqlalchemy as sa

from app.core.database import Base


class CameraPin(Base):
    """
    Camera pin model. Stored in both database AND GeoJSON map.
    Database is source of truth for metadata, GeoJSON for visualization.
    """
    __tablename__ = "camera_pins"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mall_id = Column(UUID(as_uuid=True), ForeignKey('malls.id', ondelete='CASCADE'), nullable=False, index=True)

    # Basic info
    name = Column(String(255), nullable=False)  # e.g., "cam-ENTR-01"
    label = Column(String(255), nullable=False)  # e.g., "Entrance A - Main"

    # Location (align with schema naming)
    location_lat = Column(Float, nullable=False)
    location_lng = Column(Float, nullable=False)

    # Pin type
    pin_type = Column(String(20), nullable=False, default="normal")  # entrance | normal

    # Adjacency and routing (fix mutable default)
    adjacent_to = Column(ARRAY(UUID(as_uuid=True)), nullable=True, server_default='{}')
    transit_times = Column(JSONB, nullable=True)  # {cam_id: {mu_sec: X, tau_sec: Y}}

    # Camera metadata
    store_id = Column(UUID(as_uuid=True), ForeignKey('stores.id', ondelete='SET NULL'), nullable=True, index=True)
    camera_fps = Column(Integer, nullable=False, default=15)
    camera_note = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    mall = relationship("Mall", back_populates="camera_pins")
    store = relationship("Store", back_populates="camera_pins")
    videos = relationship("Video", back_populates="camera_pin", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<CameraPin {self.name} ({self.pin_type})>"


class Video(Base):
    """
    Video footage uploaded to a camera pin.

    Phase 2 Features:
    - Multipart upload support with checksum deduplication
    - Separate original and proxy video paths
    - Extended metadata (recorded_at, operator_notes, uploader)
    - Enhanced status tracking (upload_status + processing_status)
    """
    __tablename__ = "videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mall_id = Column(UUID(as_uuid=True), ForeignKey('malls.id', ondelete='CASCADE'), nullable=False, index=True)
    pin_id = Column(UUID(as_uuid=True), ForeignKey('camera_pins.id', ondelete='CASCADE'), nullable=False, index=True)

    # Legacy field (kept for backward compatibility)
    camera_pin_id = Column(UUID(as_uuid=True), ForeignKey('camera_pins.id', ondelete='CASCADE'), nullable=False, index=True)

    # File metadata
    filename = Column(String(255), nullable=False)
    original_path = Column(String(512), nullable=True)  # S3 path: {mall_id}/{pin_id}/{video_id}/original.mp4
    proxy_path = Column(String(512), nullable=True)     # S3 path: {mall_id}/{pin_id}/{video_id}/proxy.mp4
    file_size_bytes = Column(BigInteger, nullable=False)
    duration_seconds = Column(Integer, nullable=True)
    checksum_sha256 = Column(String(64), nullable=True, index=True)  # For deduplication

    # Legacy fields (kept for backward compatibility)
    file_path = Column(String(500), nullable=True)
    original_filename = Column(String(255), nullable=True)

    # Video properties (extracted via ffprobe)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    fps = Column(sa.Numeric(5, 2), nullable=True)
    codec = Column(String(50), nullable=True)

    # Upload metadata (operator-provided)
    recorded_at = Column(DateTime, nullable=True, index=True)  # Actual CCTV recording timestamp
    operator_notes = Column(Text, nullable=True)
    uploaded_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    # Status tracking
    upload_status = Column(String(20), nullable=False, default='uploading', index=True)
        # Values: uploading, uploaded, failed
    processing_status = Column(String(50), nullable=False, default="pending", index=True)
        # Values: pending, processing, completed, failed
    processing_job_id = Column(String(255), nullable=True)
    processing_error = Column(Text, nullable=True)

    # Legacy field (kept for backward compatibility)
    processed = Column(Boolean, nullable=False, default=False)

    # Timestamps
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    processing_started_at = Column(DateTime, nullable=True)
    processing_completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Legacy field (kept for backward compatibility)
    upload_timestamp = Column(DateTime, nullable=True)

    # Relationships
    mall = relationship("Mall", back_populates="videos")
    camera_pin = relationship("CameraPin", back_populates="videos", foreign_keys=[camera_pin_id])
    pin = relationship("CameraPin", foreign_keys=[pin_id])
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_user_id])
    processing_jobs = relationship("ProcessingJob", back_populates="video", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Video {self.id} - {self.upload_status}/{self.processing_status}>"


class ProcessingJob(Base):
    """
    Background processing job tracking for video operations.

    Tracks Celery tasks for:
    - proxy_generation: FFmpeg proxy creation
    - cv_analysis: Computer vision processing (Phase 3)
    """
    __tablename__ = "processing_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(UUID(as_uuid=True), ForeignKey('videos.id', ondelete='CASCADE'), nullable=False, index=True)
    job_type = Column(String(50), nullable=False)  # 'proxy_generation', 'cv_analysis', etc.

    # Job status (coarse-grained for MVP: pending/running/completed/failed)
    status = Column(String(20), nullable=False, default='pending', index=True)
        # Values: pending, running, completed, failed, cancelled

    # Celery task tracking
    celery_task_id = Column(String(255), nullable=True, index=True)
    worker_hostname = Column(String(255), nullable=True)

    # Result and error information
    result_data = Column(JSONB, nullable=True)  # Job-specific result data
    error_message = Column(Text, nullable=True)

    # Timestamps
    queued_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    video = relationship("Video", back_populates="processing_jobs")

    def __repr__(self):
        return f"<ProcessingJob {self.id} - {self.job_type} ({self.status})>"
