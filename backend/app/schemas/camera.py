"""
Pydantic schemas for CameraPin and Video models.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# CameraPin schemas
class CameraPinBase(BaseModel):
    """Base camera pin schema."""
    name: str
    label: str
    location_lat: float = Field(..., ge=-90, le=90, description="Latitude coordinate")
    location_lng: float = Field(..., ge=-180, le=180, description="Longitude coordinate")
    pin_type: str = Field(default="normal", pattern="^(entrance|normal)$")
    mall_id: UUID


class CameraPinCreate(CameraPinBase):
    """Schema for creating a camera pin."""
    adjacent_to: List[UUID] = Field(default_factory=list)
    transit_times: Optional[Dict[str, Any]] = None
    store_id: Optional[UUID] = None
    camera_fps: int = Field(default=15, ge=1, le=60)
    camera_note: Optional[str] = None


class CameraPinUpdate(BaseModel):
    """Schema for updating a camera pin."""
    name: Optional[str] = None
    label: Optional[str] = None
    location_lat: Optional[float] = Field(None, ge=-90, le=90, description="Latitude coordinate")
    location_lng: Optional[float] = Field(None, ge=-180, le=180, description="Longitude coordinate")
    pin_type: Optional[str] = Field(None, pattern="^(entrance|normal)$")
    adjacent_to: Optional[List[UUID]] = None
    transit_times: Optional[Dict[str, Any]] = None
    store_id: Optional[UUID] = None
    camera_fps: Optional[int] = Field(None, ge=1, le=60)
    camera_note: Optional[str] = None


class CameraPin(CameraPinBase):
    """Schema for camera pin response."""
    id: UUID
    adjacent_to: List[UUID]
    transit_times: Optional[Dict[str, Any]] = None
    store_id: Optional[UUID] = None
    camera_fps: int
    camera_note: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Video schemas
class VideoBase(BaseModel):
    """Base video schema."""
    camera_pin_id: UUID


class VideoCreate(VideoBase):
    """Schema for creating a video record (after upload)."""
    file_path: str
    original_filename: str
    file_size_bytes: int = Field(..., gt=0, description="File size in bytes")
    duration_seconds: Optional[int] = None


class VideoUpdate(BaseModel):
    """Schema for updating a video."""
    processed: Optional[bool] = None
    processing_status: Optional[str] = Field(
        None, pattern="^(pending|processing|completed|failed)$"
    )
    duration_seconds: Optional[int] = None


class Video(VideoBase):
    """Schema for video response."""
    id: UUID
    file_path: str
    original_filename: str
    file_size_bytes: int
    duration_seconds: Optional[int] = None
    processed: bool
    processing_status: str
    upload_timestamp: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Video upload response
class VideoUploadResponse(BaseModel):
    """Schema for video upload response."""
    video: Video
    message: str = "Video uploaded successfully"
