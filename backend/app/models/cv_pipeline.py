"""
Computer vision pipeline models (future use - Phase 3+).
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Integer, Float, ARRAY, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base


class VisitorProfile(Base):
    """Visitor profile based on outfit characteristics."""
    __tablename__ = "visitor_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    outfit_hash = Column(String(64), nullable=False, index=True)
    detection_date = Column(DateTime, nullable=False, index=True)

    # Outfit descriptor
    outfit = Column(JSONB, nullable=False)  # {top: {type, color}, bottom: {type, color}, shoes: {type, color}}

    # Timing
    first_seen = Column(DateTime, nullable=False)
    last_seen = Column(DateTime, nullable=False)

    __table_args__ = (
        Index('ix_visitor_profile_outfit_date', 'outfit_hash', 'detection_date'),
    )

    def __repr__(self):
        return f"<VisitorProfile {self.outfit_hash}>"


class Tracklet(Base):
    """Within-camera person track with outfit features."""
    __tablename__ = "tracklets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mall_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    pin_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    video_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Track info
    track_id = Column(Integer, nullable=False)  # Camera-local ID
    t_in = Column(DateTime, nullable=False)
    t_out = Column(DateTime, nullable=False)

    # Outfit features
    outfit_vec = Column(ARRAY(Float), nullable=False)  # 64-128D embedding
    outfit_json = Column(JSONB, nullable=False)  # {top, bottom, shoes}

    # Physique attributes (non-biometric)
    physique = Column(JSONB, nullable=False)  # {height_category, aspect_ratio}

    # Bounding box statistics
    box_stats = Column(JSONB, nullable=False)  # {avg_bbox, confidence}

    # Quality score
    quality = Column(Float, nullable=False, default=0.0)

    __table_args__ = (
        Index('ix_tracklet_pin_time', 'pin_id', 't_out'),
    )

    def __repr__(self):
        return f"<Tracklet {self.id} track_{self.track_id}>"


class Association(Base):
    """Cross-camera tracklet association with scores."""
    __tablename__ = "associations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mall_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Link
    from_tracklet_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    to_tracklet_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Decision
    score = Column(Float, nullable=False)
    decision = Column(String(20), nullable=False)  # linked | new_visitor | ambiguous

    # Detailed scores
    scores = Column(JSONB, nullable=False)  # {outfit_sim, time_score, adj_score, physique_pose, final}
    components = Column(JSONB, nullable=False)  # Detailed score breakdown

    # Metadata
    candidate_count = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<Association {self.from_tracklet_id} -> {self.to_tracklet_id} ({self.decision})>"


class Journey(Base):
    """Complete visitor journey across cameras."""
    __tablename__ = "journeys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    visitor_id = Column(UUID(as_uuid=True), nullable=False, index=True)  # Links to VisitorProfile
    mall_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Journey metadata
    journey_date = Column(DateTime, nullable=False, index=True)
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime, nullable=True)
    total_duration_minutes = Column(Integer, nullable=True)

    # Confidence
    confidence = Column(Float, nullable=False)

    # Path
    path = Column(JSONB, nullable=False)  # [{camera_pin_id, camera_pin_name, arrival_time, departure_time, duration_seconds, link_score}]

    # Entry/exit points
    entry_point = Column(UUID(as_uuid=True), nullable=False, index=True)
    exit_point = Column(UUID(as_uuid=True), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index('ix_journey_date_mall', 'journey_date', 'mall_id'),
    )

    def __repr__(self):
        return f"<Journey {self.id} ({self.confidence:.2f})>"
