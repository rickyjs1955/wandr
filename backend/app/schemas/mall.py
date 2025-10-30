"""
Pydantic schemas for Mall, Store, and Tenant models.
"""
from datetime import datetime
from typing import Optional, Any, Dict
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# Mall schemas
class MallBase(BaseModel):
    """Base mall schema."""
    name: str


class MallCreate(MallBase):
    """Schema for creating a mall."""
    geojson_map: Optional[Dict[str, Any]] = None


class MallUpdate(BaseModel):
    """Schema for updating a mall."""
    name: Optional[str] = None
    geojson_map: Optional[Dict[str, Any]] = None


class Mall(MallBase):
    """Schema for mall response."""
    id: UUID
    geojson_map: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Store schemas (future use)
class StoreBase(BaseModel):
    """Base store schema."""
    name: str
    category: Optional[str] = None
    mall_id: UUID


class StoreCreate(StoreBase):
    """Schema for creating a store."""
    polygon: Optional[Dict[str, Any]] = None
    tenant_id: Optional[UUID] = None


class StoreUpdate(BaseModel):
    """Schema for updating a store."""
    name: Optional[str] = None
    category: Optional[str] = None
    polygon: Optional[Dict[str, Any]] = None
    tenant_id: Optional[UUID] = None


class Store(StoreBase):
    """Schema for store response."""
    id: UUID
    polygon: Optional[Dict[str, Any]] = None
    tenant_id: Optional[UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Tenant schemas (future use)
class TenantBase(BaseModel):
    """Base tenant schema."""
    name: str
    mall_id: UUID


class TenantCreate(TenantBase):
    """Schema for creating a tenant."""
    contact_email: Optional[str] = None
    status: str = "active"


class TenantUpdate(BaseModel):
    """Schema for updating a tenant."""
    name: Optional[str] = None
    contact_email: Optional[str] = None
    status: Optional[str] = None


class Tenant(TenantBase):
    """Schema for tenant response."""
    id: UUID
    contact_email: Optional[str] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
