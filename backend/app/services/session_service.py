"""
Redis-backed session management service.
"""
import json
import secrets
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID

import redis
from redis import Redis

from app.core.config import settings


class SessionStore:
    """Redis-backed session store for managing user sessions."""

    def __init__(self):
        """Initialize Redis connection."""
        self.redis_client: Redis = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
            health_check_interval=30
        )
        self.session_expiry = settings.SESSION_EXPIRY_SECONDS

    def generate_session_id(self) -> str:
        """
        Generate a cryptographically secure session ID.

        Returns:
            32-character hex string
        """
        return secrets.token_hex(32)

    def create_session(self, user_id: UUID, user_data: Dict[str, Any]) -> str:
        """
        Create a new session for a user.

        Args:
            user_id: UUID of the user
            user_data: Dictionary containing user information to store in session

        Returns:
            Session ID string

        Example:
            >>> session_id = session_store.create_session(
            ...     user_id=uuid4(),
            ...     user_data={"email": "user@example.com", "role": "MALL_OPERATOR"}
            ... )
        """
        session_id = self.generate_session_id()
        session_key = f"session:{session_id}"

        # Prepare session data
        session_data = {
            "user_id": str(user_id),
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
            **user_data
        }

        # Store in Redis with expiry
        self.redis_client.setex(
            session_key,
            self.session_expiry,
            json.dumps(session_data)
        )

        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session data by session ID.

        Args:
            session_id: Session ID to look up

        Returns:
            Dictionary with session data, or None if session doesn't exist or expired

        Example:
            >>> data = session_store.get_session(session_id)
            >>> if data:
            ...     print(f"User ID: {data['user_id']}")
        """
        session_key = f"session:{session_id}"
        data = self.redis_client.get(session_key)

        if data:
            session_data = json.loads(data)
            # Update last activity time
            session_data["last_activity"] = datetime.utcnow().isoformat()
            # Refresh expiry on activity
            self.redis_client.setex(
                session_key,
                self.session_expiry,
                json.dumps(session_data)
            )
            return session_data

        return None

    def update_session(self, session_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Update session data.

        Args:
            session_id: Session ID to update
            update_data: Dictionary with fields to update

        Returns:
            True if session was updated, False if session doesn't exist

        Example:
            >>> session_store.update_session(
            ...     session_id,
            ...     {"last_login": datetime.utcnow().isoformat()}
            ... )
        """
        session_key = f"session:{session_id}"
        data = self.redis_client.get(session_key)

        if not data:
            return False

        session_data = json.loads(data)
        session_data.update(update_data)
        session_data["last_activity"] = datetime.utcnow().isoformat()

        self.redis_client.setex(
            session_key,
            self.session_expiry,
            json.dumps(session_data)
        )

        return True

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session (logout).

        Args:
            session_id: Session ID to delete

        Returns:
            True if session was deleted, False if it didn't exist

        Example:
            >>> session_store.delete_session(session_id)
        """
        session_key = f"session:{session_id}"
        result = self.redis_client.delete(session_key)
        return result > 0

    def delete_user_sessions(self, user_id: UUID) -> int:
        """
        Delete all sessions for a specific user.

        Args:
            user_id: UUID of the user

        Returns:
            Number of sessions deleted

        Example:
            >>> count = session_store.delete_user_sessions(user_id)
            >>> print(f"Deleted {count} sessions")
        """
        # Find all session keys
        pattern = "session:*"
        deleted_count = 0

        for key in self.redis_client.scan_iter(match=pattern):
            data = self.redis_client.get(key)
            if data:
                session_data = json.loads(data)
                if session_data.get("user_id") == str(user_id):
                    self.redis_client.delete(key)
                    deleted_count += 1

        return deleted_count

    def session_exists(self, session_id: str) -> bool:
        """
        Check if a session exists.

        Args:
            session_id: Session ID to check

        Returns:
            True if session exists, False otherwise
        """
        session_key = f"session:{session_id}"
        return self.redis_client.exists(session_key) > 0

    def extend_session(self, session_id: str, additional_seconds: int = None) -> bool:
        """
        Extend session expiry time.

        Args:
            session_id: Session ID to extend
            additional_seconds: Additional seconds to add (default: reset to full expiry)

        Returns:
            True if session was extended, False if it doesn't exist
        """
        session_key = f"session:{session_id}"

        if not self.session_exists(session_id):
            return False

        expiry = additional_seconds if additional_seconds else self.session_expiry
        self.redis_client.expire(session_key, expiry)
        return True

    def get_active_session_count(self) -> int:
        """
        Get the count of active sessions.

        Returns:
            Number of active sessions
        """
        pattern = "session:*"
        return len(list(self.redis_client.scan_iter(match=pattern)))

    def health_check(self) -> bool:
        """
        Check if Redis connection is healthy.

        Returns:
            True if Redis is responding, False otherwise
        """
        try:
            self.redis_client.ping()
            return True
        except Exception:
            return False


# Global session store instance
session_store = SessionStore()
