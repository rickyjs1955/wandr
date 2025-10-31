"""
SQLAlchemy ORM models.
"""
from app.models.user import User, UserRole
from app.models.mall import Mall, Store, Tenant
from app.models.camera import CameraPin, Video, ProcessingJob
from app.models.cv_pipeline import VisitorProfile, Tracklet, Association, Journey

__all__ = [
    # User models
    "User",
    "UserRole",
    # Mall models
    "Mall",
    "Store",
    "Tenant",
    # Camera models
    "CameraPin",
    "Video",
    "ProcessingJob",
    # CV Pipeline models (future use)
    "VisitorProfile",
    "Tracklet",
    "Association",
    "Journey",
]
