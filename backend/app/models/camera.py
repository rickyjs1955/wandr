"""
Camera pin and video models.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Integer, Float, Boolean, ARRAY, Text, ForeignKey, BigInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

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
    """Video footage uploaded to a camera pin."""
    __tablename__ = "videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_pin_id = Column(UUID(as_uuid=True), ForeignKey('camera_pins.id', ondelete='CASCADE'), nullable=False, index=True)

    # File info
    file_path = Column(String(500), nullable=False)  # Path in MinIO/S3
    original_filename = Column(String(255), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    duration_seconds = Column(Integer, nullable=True)

    # Processing
    processed = Column(Boolean, nullable=False, default=False)
    processing_status = Column(String(50), nullable=False, default="pending", index=True)  # pending | processing | completed | failed

    # Timestamps
    upload_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    camera_pin = relationship("CameraPin", back_populates="videos")

    def __repr__(self):
        return f"<Video {self.id} - {self.processing_status}>"
