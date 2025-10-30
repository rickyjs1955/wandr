"""
Pydantic schemas for CV Pipeline models (future use - Phase 3+).
"""
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# VisitorProfile schemas
class VisitorProfileBase(BaseModel):
    """Base visitor profile schema."""
    outfit_hash: str = Field(..., max_length=64)
    detection_date: date  # Changed from datetime to date for day-level analytics
    outfit: Dict[str, Any]


class VisitorProfileCreate(VisitorProfileBase):
    """Schema for creating a visitor profile."""
    first_seen: datetime
    last_seen: datetime


class VisitorProfile(VisitorProfileBase):
    """Schema for visitor profile response."""
    id: UUID
    first_seen: datetime
    last_seen: datetime

    model_config = ConfigDict(from_attributes=True)


# Tracklet schemas
class TrackletBase(BaseModel):
    """Base tracklet schema."""
    mall_id: UUID
    pin_id: UUID
    video_id: UUID
    track_id: int


class TrackletCreate(TrackletBase):
    """Schema for creating a tracklet."""
    t_in: datetime
    t_out: datetime
    outfit_vec: List[float]
    outfit_json: Dict[str, Any]
    physique: Dict[str, Any]
    box_stats: Dict[str, Any]
    quality: float = Field(..., ge=0, le=1)


class Tracklet(TrackletBase):
    """Schema for tracklet response."""
    id: UUID
    t_in: datetime
    t_out: datetime
    outfit_vec: List[float]
    outfit_json: Dict[str, Any]
    physique: Dict[str, Any]
    box_stats: Dict[str, Any]
    quality: float

    model_config = ConfigDict(from_attributes=True)


# Association schemas
class AssociationBase(BaseModel):
    """Base association schema."""
    mall_id: UUID
    from_tracklet_id: UUID
    to_tracklet_id: UUID


class AssociationCreate(AssociationBase):
    """Schema for creating an association."""
    score: float = Field(..., ge=0, le=1)
    decision: str = Field(..., pattern="^(linked|new_visitor|ambiguous)$")
    scores: Dict[str, float]
    components: Dict[str, Any]
    candidate_count: int


class Association(AssociationBase):
    """Schema for association response."""
    id: UUID
    score: float
    decision: str
    scores: Dict[str, float]
    components: Dict[str, Any]
    candidate_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Journey schemas
class JourneyStep(BaseModel):
    """Schema for a single journey step."""
    camera_pin_id: UUID
    camera_pin_name: str
    arrival_time: datetime
    departure_time: datetime
    duration_seconds: int
    link_score: Optional[float] = Field(None, ge=0, le=1)


class JourneyBase(BaseModel):
    """Base journey schema."""
    visitor_id: UUID
    mall_id: UUID
    journey_date: date  # Changed from datetime to date for day-level analytics


class JourneyCreate(JourneyBase):
    """Schema for creating a journey."""
    entry_time: datetime
    exit_time: Optional[datetime] = None
    total_duration_minutes: Optional[int] = None
    confidence: float = Field(..., ge=0, le=1)
    path: List[Dict[str, Any]]
    entry_point: UUID
    exit_point: Optional[UUID] = None


class Journey(JourneyBase):
    """Schema for journey response."""
    id: UUID
    entry_time: datetime
    exit_time: Optional[datetime] = None
    total_duration_minutes: Optional[int] = None
    confidence: float
    path: List[Dict[str, Any]]
    entry_point: UUID
    exit_point: Optional[UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Journey query filters
class JourneyFilters(BaseModel):
    """Schema for journey query filters."""
    from_date: Optional[date] = None  # Changed from datetime to date
    to_date: Optional[date] = None  # Changed from datetime to date
    min_confidence: Optional[float] = Field(None, ge=0, le=1)
    entry_pin: Optional[UUID] = None
