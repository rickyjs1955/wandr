"""
Pydantic schemas for User model validation.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
import re

from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator

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
    password: str = Field(..., min_length=8, max_length=128, description="Password must be at least 8 characters")
    mall_id: Optional[UUID] = None
    tenant_id: Optional[UUID] = None

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """
        Validate password meets security requirements:
        - At least 8 characters
        - Contains at least one uppercase letter
        - Contains at least one lowercase letter
        - Contains at least one digit
        - Contains at least one special character
        """
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')

        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')

        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')

        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')

        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')

        return v


# Properties to receive on user update
class UserUpdate(BaseModel):
    """Schema for updating a user."""
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8, max_length=128, description="Password must be at least 8 characters")
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    mall_id: Optional[UUID] = None
    tenant_id: Optional[UUID] = None

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate password meets security requirements if provided.
        """
        if v is None:
            return v

        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')

        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')

        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')

        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')

        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')

        return v


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
