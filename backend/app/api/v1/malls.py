"""
Mall management API endpoints.
Handles mall details, GeoJSON maps, and mall-related operations.
"""

from typing import Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.mall import Mall
from app.schemas.mall import (
    Mall as MallSchema,
    MallCreate,
    MallUpdate,
    GeoJSONMap,
)
from app.api.v1.auth import get_current_user

router = APIRouter()


@router.get("/{mall_id}", response_model=MallSchema)
async def get_mall(
    mall_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get mall details by ID.

    Requires authentication. Users can only access their own mall.
    """
    # Verify user has access to this mall
    if current_user.mall_id != mall_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this mall",
        )

    mall = db.query(Mall).filter(Mall.id == mall_id).first()
    if not mall:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mall not found",
        )

    return mall


@router.get("/{mall_id}/map", response_model=GeoJSONMap)
async def get_mall_map(
    mall_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get mall's GeoJSON map.

    Returns the GeoJSON FeatureCollection for the mall's floor plan.
    """
    # Verify user has access to this mall
    if current_user.mall_id != mall_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this mall",
        )

    mall = db.query(Mall).filter(Mall.id == mall_id).first()
    if not mall:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mall not found",
        )

    if not mall.geojson_map:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No map found for this mall",
        )

    return {"geojson": mall.geojson_map}


@router.put("/{mall_id}/map", response_model=GeoJSONMap)
async def update_mall_map(
    mall_id: UUID,
    geojson_data: GeoJSONMap,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload or update mall's GeoJSON map.

    Validates GeoJSON structure and stores it in the database.
    """
    # Verify user has access to this mall
    if current_user.mall_id != mall_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this mall",
        )

    mall = db.query(Mall).filter(Mall.id == mall_id).first()
    if not mall:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mall not found",
        )

    # Validate GeoJSON structure
    geojson = geojson_data.geojson
    if not isinstance(geojson, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid GeoJSON: must be a JSON object",
        )

    if geojson.get("type") != "FeatureCollection":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid GeoJSON: must be a FeatureCollection",
        )

    if "features" not in geojson:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid GeoJSON: missing 'features' array",
        )

    # Update mall map
    mall.geojson_map = geojson
    db.commit()
    db.refresh(mall)

    return {"geojson": mall.geojson_map}


@router.patch("/{mall_id}", response_model=MallSchema)
async def update_mall(
    mall_id: UUID,
    mall_update: MallUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update mall details (name, etc).

    Partial update - only provided fields are updated.
    """
    # Verify user has access to this mall
    if current_user.mall_id != mall_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this mall",
        )

    mall = db.query(Mall).filter(Mall.id == mall_id).first()
    if not mall:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mall not found",
        )

    # Update only provided fields
    update_data = mall_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(mall, field, value)

    db.commit()
    db.refresh(mall)

    return mall
