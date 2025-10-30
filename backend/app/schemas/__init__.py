"""
Pydantic schemas for request/response validation.
"""
from app.schemas.user import (
    User,
    UserCreate,
    UserUpdate,
    UserLogin,
    UserLoginResponse,
    UserInDB,
)
from app.schemas.mall import (
    Mall,
    MallCreate,
    MallUpdate,
    Store,
    StoreCreate,
    StoreUpdate,
    Tenant,
    TenantCreate,
    TenantUpdate,
)
from app.schemas.camera import (
    CameraPin,
    CameraPinCreate,
    CameraPinUpdate,
    Video,
    VideoCreate,
    VideoUpdate,
    VideoUploadResponse,
)
from app.schemas.cv_pipeline import (
    VisitorProfile,
    VisitorProfileCreate,
    Tracklet,
    TrackletCreate,
    Association,
    AssociationCreate,
    Journey,
    JourneyCreate,
    JourneyStep,
    JourneyFilters,
)

__all__ = [
    # User schemas
    "User",
    "UserCreate",
    "UserUpdate",
    "UserLogin",
    "UserLoginResponse",
    "UserInDB",
    # Mall schemas
    "Mall",
    "MallCreate",
    "MallUpdate",
    "Store",
    "StoreCreate",
    "StoreUpdate",
    "Tenant",
    "TenantCreate",
    "TenantUpdate",
    # Camera schemas
    "CameraPin",
    "CameraPinCreate",
    "CameraPinUpdate",
    "Video",
    "VideoCreate",
    "VideoUpdate",
    "VideoUploadResponse",
    # CV Pipeline schemas (future use)
    "VisitorProfile",
    "VisitorProfileCreate",
    "Tracklet",
    "TrackletCreate",
    "Association",
    "AssociationCreate",
    "Journey",
    "JourneyCreate",
    "JourneyStep",
    "JourneyFilters",
]
