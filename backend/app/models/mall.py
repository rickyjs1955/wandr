"""
Mall and Store models.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

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

    # Relationships
    users = relationship("User", back_populates="mall")
    camera_pins = relationship("CameraPin", back_populates="mall", cascade="all, delete-orphan")
    stores = relationship("Store", back_populates="mall", cascade="all, delete-orphan")
    tenants = relationship("Tenant", back_populates="mall", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Mall {self.name}>"


class Store(Base):
    """Store/tenant location model (future use)."""
    __tablename__ = "stores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mall_id = Column(UUID(as_uuid=True), ForeignKey('malls.id', ondelete='CASCADE'), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)
    polygon = Column(JSONB, nullable=True)  # GeoJSON polygon for store location
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='SET NULL'), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    mall = relationship("Mall", back_populates="stores")
    tenant = relationship("Tenant", back_populates="stores")
    camera_pins = relationship("CameraPin", back_populates="store")

    def __repr__(self):
        return f"<Store {self.name}>"


class Tenant(Base):
    """Tenant/retailer model (future use)."""
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mall_id = Column(UUID(as_uuid=True), ForeignKey('malls.id', ondelete='CASCADE'), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    contact_email = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default="active")  # active, inactive

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    mall = relationship("Mall", back_populates="tenants")
    users = relationship("User", back_populates="tenant")
    stores = relationship("Store", back_populates="tenant")

    def __repr__(self):
        return f"<Tenant {self.name}>"
