"""
Camera Pin management API endpoints.
Handles CRUD operations for camera pins and adjacency relationships.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.camera import CameraPin
from app.models.mall import Mall
from app.schemas.camera import (
    CameraPin as CameraPinSchema,
    CameraPinCreate,
    CameraPinUpdate,
)
from app.api.v1.auth import get_current_user

router = APIRouter()


@router.get("/", response_model=List[CameraPinSchema])
async def list_pins(
    mall_id: UUID,
    pin_type: str = Query(None, description="Filter by pin type: entrance or normal"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all camera pins for a mall.

    Optional filtering by pin_type.
    """
    # Verify user has access to this mall
    if current_user.mall_id != mall_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this mall",
        )

    # Verify mall exists
    mall = db.query(Mall).filter(Mall.id == mall_id).first()
    if not mall:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mall not found",
        )

    # Build query
    query = db.query(CameraPin).filter(CameraPin.mall_id == mall_id)

    # Apply filter if provided
    if pin_type:
        if pin_type not in ["entrance", "normal"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid pin_type. Must be 'entrance' or 'normal'",
            )
        query = query.filter(CameraPin.pin_type == pin_type)

    pins = query.order_by(CameraPin.created_at).all()
    return pins


@router.post("/", response_model=CameraPinSchema, status_code=status.HTTP_201_CREATED)
async def create_pin(
    mall_id: UUID,
    pin_data: CameraPinCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new camera pin.

    Validates coordinates and adjacency references.
    """
    # Verify user has access to this mall
    if current_user.mall_id != mall_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this mall",
        )

    # Verify mall exists
    mall = db.query(Mall).filter(Mall.id == mall_id).first()
    if not mall:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mall not found",
        )

    # Validate coordinates
    if not (-90 <= pin_data.latitude <= 90):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid latitude. Must be between -90 and 90",
        )

    if not (-180 <= pin_data.longitude <= 180):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid longitude. Must be between -180 and 180",
        )

    # Validate adjacent pins exist (if provided)
    if pin_data.adjacent_to:
        for adjacent_id in pin_data.adjacent_to:
            adjacent_pin = (
                db.query(CameraPin)
                .filter(
                    CameraPin.id == adjacent_id,
                    CameraPin.mall_id == mall_id,
                )
                .first()
            )
            if not adjacent_pin:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Adjacent pin {adjacent_id} not found in this mall",
                )

    # Check for duplicate name in this mall
    existing_pin = (
        db.query(CameraPin)
        .filter(
            CameraPin.mall_id == mall_id,
            CameraPin.name == pin_data.name,
        )
        .first()
    )
    if existing_pin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pin with name '{pin_data.name}' already exists in this mall",
        )

    # Create pin
    pin = CameraPin(
        mall_id=mall_id,
        **pin_data.model_dump(),
    )

    db.add(pin)
    db.commit()
    db.refresh(pin)

    return pin


@router.get("/{pin_id}", response_model=CameraPinSchema)
async def get_pin(
    mall_id: UUID,
    pin_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get camera pin details by ID.
    """
    # Verify user has access to this mall
    if current_user.mall_id != mall_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this mall",
        )

    pin = (
        db.query(CameraPin)
        .filter(
            CameraPin.id == pin_id,
            CameraPin.mall_id == mall_id,
        )
        .first()
    )

    if not pin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera pin not found",
        )

    return pin


@router.patch("/{pin_id}", response_model=CameraPinSchema)
async def update_pin(
    mall_id: UUID,
    pin_id: UUID,
    pin_update: CameraPinUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update camera pin details.

    Partial update - only provided fields are updated.
    """
    # Verify user has access to this mall
    if current_user.mall_id != mall_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this mall",
        )

    pin = (
        db.query(CameraPin)
        .filter(
            CameraPin.id == pin_id,
            CameraPin.mall_id == mall_id,
        )
        .first()
    )

    if not pin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera pin not found",
        )

    # Update only provided fields
    update_data = pin_update.model_dump(exclude_unset=True)

    # Validate coordinates if provided
    if "latitude" in update_data:
        if not (-90 <= update_data["latitude"] <= 90):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid latitude. Must be between -90 and 90",
            )

    if "longitude" in update_data:
        if not (-180 <= update_data["longitude"] <= 180):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid longitude. Must be between -180 and 180",
            )

    # Validate adjacent pins if provided
    if "adjacent_to" in update_data:
        for adjacent_id in update_data["adjacent_to"]:
            # Prevent self-adjacency
            if adjacent_id == pin_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Pin cannot be adjacent to itself",
                )

            adjacent_pin = (
                db.query(CameraPin)
                .filter(
                    CameraPin.id == adjacent_id,
                    CameraPin.mall_id == mall_id,
                )
                .first()
            )
            if not adjacent_pin:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Adjacent pin {adjacent_id} not found in this mall",
                )

    # Check for duplicate name if name is being updated
    if "name" in update_data and update_data["name"] != pin.name:
        existing_pin = (
            db.query(CameraPin)
            .filter(
                CameraPin.mall_id == mall_id,
                CameraPin.name == update_data["name"],
                CameraPin.id != pin_id,
            )
            .first()
        )
        if existing_pin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Pin with name '{update_data['name']}' already exists in this mall",
            )

    # Apply updates
    for field, value in update_data.items():
        setattr(pin, field, value)

    db.commit()
    db.refresh(pin)

    return pin


@router.delete("/{pin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pin(
    mall_id: UUID,
    pin_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a camera pin.

    CASCADE deletes associated videos and tracklets.
    """
    # Verify user has access to this mall
    if current_user.mall_id != mall_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this mall",
        )

    pin = (
        db.query(CameraPin)
        .filter(
            CameraPin.id == pin_id,
            CameraPin.mall_id == mall_id,
        )
        .first()
    )

    if not pin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera pin not found",
        )

    # Remove this pin from other pins' adjacent_to lists
    other_pins = (
        db.query(CameraPin)
        .filter(CameraPin.mall_id == mall_id)
        .all()
    )

    for other_pin in other_pins:
        if pin_id in (other_pin.adjacent_to or []):
            adjacent_list = list(other_pin.adjacent_to)
            adjacent_list.remove(pin_id)
            other_pin.adjacent_to = adjacent_list

    # Delete the pin (CASCADE will delete videos, tracklets)
    db.delete(pin)
    db.commit()

    return None
