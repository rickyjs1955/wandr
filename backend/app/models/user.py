"""
User model for authentication and authorization.
"""
import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, String, DateTime, Boolean, Enum as SQLEnum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class UserRole(str, Enum):
    """User roles for RBAC."""
    MALL_OPERATOR = "MALL_OPERATOR"
    TENANT_MANAGER = "TENANT_MANAGER"  # Future use
    TENANT_VIEWER = "TENANT_VIEWER"  # Future use


class User(Base):
    """User model for mall operators and tenant users."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.MALL_OPERATOR)
    is_active = Column(Boolean, nullable=False, default=True)

    # Foreign keys with constraints
    mall_id = Column(UUID(as_uuid=True), ForeignKey('malls.id', ondelete='CASCADE'), nullable=True, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='SET NULL'), nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Relationships
    mall = relationship("Mall", back_populates="users")
    tenant = relationship("Tenant", back_populates="users")

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"
