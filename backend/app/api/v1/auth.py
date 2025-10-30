"""
Authentication API endpoints.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, Cookie, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User as UserModel
from app.schemas.user import UserLogin, User, UserLoginResponse
from app.services import hash_password, verify_password, session_store

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=UserLoginResponse, status_code=status.HTTP_200_OK)
async def login(
    credentials: UserLogin,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and create session.

    - **username**: Username or email
    - **password**: User's password

    Returns user object and sets session cookie.
    """
    # Find user by username or email
    user = db.query(UserModel).filter(
        (UserModel.username == credentials.username) |
        (UserModel.email == credentials.username)
    ).first()

    # Verify user exists and password is correct
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    # Check if user account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Please contact administrator."
        )

    # Create session
    session_data = {
        "email": user.email,
        "username": user.username,
        "role": user.role.value,
        "mall_id": str(user.mall_id) if user.mall_id else None,
        "tenant_id": str(user.tenant_id) if user.tenant_id else None,
    }

    session_id = session_store.create_session(user.id, session_data)

    # Set session cookie (HttpOnly, Secure in production, SameSite)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=not settings.DEBUG,  # HTTPS only in production
        samesite="lax",
        max_age=settings.SESSION_EXPIRY_SECONDS
    )

    # Update last login timestamp
    from datetime import datetime
    user.last_login = datetime.utcnow()
    db.commit()

    return UserLoginResponse(
        user=User.model_validate(user),
        message="Login successful"
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    response: Response,
    session_id: Optional[str] = Cookie(None, alias=settings.SESSION_COOKIE_NAME)
):
    """
    Logout user and destroy session.

    Clears session cookie and removes session from Redis.
    """
    if session_id:
        session_store.delete_session(session_id)

    # Clear session cookie
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax"
    )

    return {"message": "Logout successful"}


@router.get("/me", response_model=User)
async def get_current_user(
    session_id: Optional[str] = Cookie(None, alias=settings.SESSION_COOKIE_NAME),
    db: Session = Depends(get_db)
):
    """
    Get currently authenticated user.

    Returns user object if valid session exists, otherwise returns 401.
    """
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    # Get session data
    session_data = session_store.get_session(session_id)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid"
        )

    # Get user from database
    user_id = UUID(session_data["user_id"])
    user = db.query(UserModel).filter(UserModel.id == user_id).first()

    if not user:
        # Session exists but user was deleted
        session_store.delete_session(session_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )

    return User.model_validate(user)


@router.post("/refresh", status_code=status.HTTP_200_OK)
async def refresh_session(
    response: Response,
    session_id: Optional[str] = Cookie(None, alias=settings.SESSION_COOKIE_NAME)
):
    """
    Refresh session expiry.

    Extends session expiry time by the configured duration.
    """
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    if not session_store.session_exists(session_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid"
        )

    # Extend session
    session_store.extend_session(session_id)

    # Refresh cookie
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.SESSION_EXPIRY_SECONDS
    )

    return {"message": "Session refreshed"}


@router.get("/health", status_code=status.HTTP_200_OK)
async def auth_health_check():
    """
    Check authentication service health.

    Returns Redis connection status and session store health.
    """
    redis_healthy = session_store.health_check()
    active_sessions = session_store.get_active_session_count() if redis_healthy else 0

    return {
        "status": "healthy" if redis_healthy else "unhealthy",
        "redis_connected": redis_healthy,
        "active_sessions": active_sessions
    }
