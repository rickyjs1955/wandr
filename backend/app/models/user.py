"""
User model for authentication and authorization.
"""
import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, String, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID

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

    # Foreign keys
    mall_id = Column(UUID(as_uuid=True), nullable=True)  # Set after mall creation
    tenant_id = Column(UUID(as_uuid=True), nullable=True)  # Future use

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"
