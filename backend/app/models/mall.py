"""
Mall and Store models.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base


class Mall(Base):
    """Mall model with GeoJSON map data."""
    __tablename__ = "malls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    geojson_map = Column(JSONB, nullable=True)  # Complete GeoJSON with camera pins

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Mall {self.name}>"


class Store(Base):
    """Store/tenant location model (future use)."""
    __tablename__ = "stores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mall_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)
    polygon = Column(JSONB, nullable=True)  # GeoJSON polygon for store location
    tenant_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<Store {self.name}>"


class Tenant(Base):
    """Tenant/retailer model (future use)."""
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mall_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    contact_email = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default="active")  # active, inactive

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<Tenant {self.name}>"
