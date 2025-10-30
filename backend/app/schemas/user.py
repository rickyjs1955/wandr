"""
Pydantic schemas for User model validation.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, ConfigDict

from app.models.user import UserRole


# Shared properties
class UserBase(BaseModel):
    """Base user schema with common fields."""
    email: EmailStr
    username: str
    role: UserRole = UserRole.MALL_OPERATOR


# Properties to receive on user creation
class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str
    mall_id: Optional[UUID] = None
    tenant_id: Optional[UUID] = None


# Properties to receive on user update
class UserUpdate(BaseModel):
    """Schema for updating a user."""
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    mall_id: Optional[UUID] = None
    tenant_id: Optional[UUID] = None


# Properties shared by models stored in DB
class UserInDBBase(UserBase):
    """Base schema for user in database."""
    id: UUID
    is_active: bool
    mall_id: Optional[UUID] = None
    tenant_id: Optional[UUID] = None
    created_at: datetime
    last_login: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# Properties to return to client
class User(UserInDBBase):
    """Schema for user response (excludes password_hash)."""
    pass


# Properties stored in DB (includes password_hash)
class UserInDB(UserInDBBase):
    """Complete user schema as stored in database."""
    password_hash: str


# Login request
class UserLogin(BaseModel):
    """Schema for login request."""
    username: str
    password: str


# Login response
class UserLoginResponse(BaseModel):
    """Schema for login response."""
    user: User
    message: str = "Login successful"
