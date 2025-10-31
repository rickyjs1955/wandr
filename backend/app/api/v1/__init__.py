"""
API v1 router aggregation.
"""
from fastapi import APIRouter

from app.api.v1 import auth, malls, pins, videos

api_router = APIRouter()

# Include all v1 routers
api_router.include_router(auth.router)
api_router.include_router(malls.router, prefix="/malls", tags=["malls"])
api_router.include_router(pins.router, prefix="/malls/{mall_id}/pins", tags=["camera-pins"])
api_router.include_router(videos.router)

__all__ = ["api_router"]
