"""
API v1 router aggregation.
"""
from fastapi import APIRouter

from app.api.v1 import auth

api_router = APIRouter()

# Include all v1 routers
api_router.include_router(auth.router)

__all__ = ["api_router"]
