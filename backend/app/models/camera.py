"""
Camera pin and video models.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Integer, Float, Boolean, ARRAY, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base


class CameraPin(Base):
    """
    Camera pin model. Stored in both database AND GeoJSON map.
    Database is source of truth for metadata, GeoJSON for visualization.
    """
    __tablename__ = "camera_pins"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mall_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Basic info
    name = Column(String(255), nullable=False)  # e.g., "cam-ENTR-01"
    label = Column(String(255), nullable=False)  # e.g., "Entrance A - Main"

    # Location
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # Pin type
    pin_type = Column(String(20), nullable=False, default="normal")  # entrance | normal

    # Adjacency and routing
    adjacent_to = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    transit_times = Column(JSONB, nullable=True)  # {cam_id: {mu_sec: X, tau_sec: Y}}

    # Camera metadata
    store_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    camera_fps = Column(Integer, nullable=False, default=15)
    camera_note = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<CameraPin {self.name} ({self.pin_type})>"


class Video(Base):
    """Video footage uploaded to a camera pin."""
    __tablename__ = "videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_pin_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # File info
    file_path = Column(String(500), nullable=False)  # Path in MinIO/S3
    duration_seconds = Column(Integer, nullable=True)

    # Processing
    processed = Column(Boolean, nullable=False, default=False)
    processing_status = Column(String(20), nullable=False, default="pending")  # pending | processing | completed | failed

    # Timestamps
    upload_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<Video {self.id} - {self.processing_status}>"
