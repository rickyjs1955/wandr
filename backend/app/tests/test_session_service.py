"""
Unit tests for session management service.

Tests session creation, retrieval, deletion, and expiry handling.
"""

import pytest
import time
import uuid
from unittest.mock import Mock, patch
from app.services.session_service import SessionStore


@pytest.fixture
def mock_redis():
    """Create a mock Redis client for testing."""
    redis_mock = Mock()
    redis_mock.setex = Mock(return_value=True)
    redis_mock.get = Mock(return_value=None)
    redis_mock.delete = Mock(return_value=1)
    redis_mock.keys = Mock(return_value=[])
    redis_mock.ping = Mock(return_value=True)
    return redis_mock


@pytest.fixture
def session_store(mock_redis):
    """Create a SessionStore instance with mocked Redis."""
    with patch('app.services.session_service.redis.from_url', return_value=mock_redis):
        store = SessionStore()
        store.redis_client = mock_redis
        return store


@pytest.mark.unit
class TestSessionCreation:
    """Test session creation."""

    def test_generate_session_id_returns_string(self, session_store):
        """Test that session ID generation returns a string."""
        session_id = session_store.generate_session_id()
        assert isinstance(session_id, str)
        assert len(session_id) == 64  # 32 bytes * 2 (hex encoding)

    def test_generate_session_id_unique(self, session_store):
        """Test that generated session IDs are unique."""
        ids = [session_store.generate_session_id() for _ in range(100)]
        assert len(ids) == len(set(ids)), "Session IDs should be unique"

    def test_create_session_returns_session_id(self, session_store):
        """Test that create_session returns a session ID."""
        user_id = uuid.uuid4()
        user_data = {"email": "test@example.com", "role": "MALL_OPERATOR"}

        session_id = session_store.create_session(user_id, user_data)

        assert isinstance(session_id, str)
        assert len(session_id) == 64
        session_store.redis_client.setex.assert_called_once()

    def test_create_session_stores_user_data(self, session_store, mock_redis):
        """Test that create_session stores user data correctly."""
        import json

        user_id = uuid.uuid4()
        user_data = {"email": "test@example.com", "role": "MALL_OPERATOR"}

        session_store.create_session(user_id, user_data)

        # Check that setex was called with correct data
        call_args = mock_redis.setex.call_args
        session_key = call_args[0][0]
        expiry = call_args[0][1]
        stored_data = json.loads(call_args[0][2])

        assert session_key.startswith("session:")
        assert expiry == session_store.session_expiry
        assert stored_data["user_id"] == str(user_id)
        assert stored_data["email"] == user_data["email"]
        assert stored_data["role"] == user_data["role"]
        assert "created_at" in stored_data
        assert "last_activity" in stored_data


@pytest.mark.unit
class TestSessionRetrieval:
    """Test session retrieval."""

    def test_get_session_with_valid_session(self, session_store, mock_redis):
        """Test retrieving a valid session."""
        import json

        session_id = "a" * 64
        session_data = {
            "user_id": str(uuid.uuid4()),
            "email": "test@example.com",
            "created_at": "2025-01-01T00:00:00",
            "last_activity": "2025-01-01T00:00:00",
        }

        mock_redis.get.return_value = json.dumps(session_data)

        result = session_store.get_session(session_id)

        assert result is not None
        assert result["user_id"] == session_data["user_id"]
        assert result["email"] == session_data["email"]
        # last_activity should be updated
        assert result["last_activity"] != session_data["last_activity"]

    def test_get_session_with_invalid_session(self, session_store, mock_redis):
        """Test retrieving a non-existent session."""
        mock_redis.get.return_value = None

        result = session_store.get_session("invalid_session_id")

        assert result is None

    def test_get_session_refreshes_expiry(self, session_store, mock_redis):
        """Test that get_session refreshes the session expiry."""
        import json

        session_id = "a" * 64
        session_data = {
            "user_id": str(uuid.uuid4()),
            "email": "test@example.com",
            "created_at": "2025-01-01T00:00:00",
            "last_activity": "2025-01-01T00:00:00",
        }

        mock_redis.get.return_value = json.dumps(session_data)

        session_store.get_session(session_id)

        # Should call setex to refresh expiry
        assert mock_redis.setex.call_count >= 1


@pytest.mark.unit
class TestSessionDeletion:
    """Test session deletion."""

    def test_delete_session_returns_true_on_success(self, session_store, mock_redis):
        """Test that delete_session returns True when session is deleted."""
        mock_redis.delete.return_value = 1

        result = session_store.delete_session("session_id")

        assert result is True
        mock_redis.delete.assert_called_once_with("session:session_id")

    def test_delete_session_returns_false_when_not_found(self, session_store, mock_redis):
        """Test that delete_session returns False when session doesn't exist."""
        mock_redis.delete.return_value = 0

        result = session_store.delete_session("nonexistent_id")

        assert result is False

    def test_delete_user_sessions_deletes_all_user_sessions(self, session_store, mock_redis):
        """Test that delete_user_sessions removes all sessions for a user."""
        user_id = uuid.uuid4()
        mock_redis.keys.return_value = [
            b"session:abc123",
            b"session:def456",
        ]
        mock_redis.get.side_effect = [
            f'{{"user_id": "{user_id}"}}',
            f'{{"user_id": "{user_id}"}}',
        ]
        mock_redis.delete.return_value = 1

        count = session_store.delete_user_sessions(user_id)

        assert count == 2
        assert mock_redis.delete.call_count == 2


@pytest.mark.unit
class TestSessionExtension:
    """Test session extension."""

    def test_extend_session_with_valid_session(self, session_store, mock_redis):
        """Test extending a valid session."""
        import json

        session_id = "a" * 64
        session_data = {
            "user_id": str(uuid.uuid4()),
            "email": "test@example.com",
            "created_at": "2025-01-01T00:00:00",
            "last_activity": "2025-01-01T00:00:00",
        }

        mock_redis.get.return_value = json.dumps(session_data)

        result = session_store.extend_session(session_id)

        assert result is True
        # Should call setex to extend expiry
        mock_redis.setex.assert_called()

    def test_extend_session_with_invalid_session(self, session_store, mock_redis):
        """Test extending a non-existent session."""
        mock_redis.get.return_value = None

        result = session_store.extend_session("invalid_session_id")

        assert result is False

    def test_session_exists_with_valid_session(self, session_store, mock_redis):
        """Test checking if a session exists."""
        mock_redis.get.return_value = '{"user_id": "123"}'

        result = session_store.session_exists("session_id")

        assert result is True

    def test_session_exists_with_invalid_session(self, session_store, mock_redis):
        """Test checking if a non-existent session exists."""
        mock_redis.get.return_value = None

        result = session_store.session_exists("invalid_id")

        assert result is False


@pytest.mark.unit
class TestSessionHealth:
    """Test session service health checks."""

    def test_health_check_with_healthy_redis(self, session_store, mock_redis):
        """Test health check with healthy Redis connection."""
        mock_redis.ping.return_value = True

        result = session_store.health_check()

        assert result is True
        mock_redis.ping.assert_called_once()

    def test_health_check_with_unhealthy_redis(self, session_store, mock_redis):
        """Test health check with unhealthy Redis connection."""
        mock_redis.ping.side_effect = Exception("Connection failed")

        result = session_store.health_check()

        assert result is False

    def test_get_active_session_count(self, session_store, mock_redis):
        """Test getting active session count."""
        mock_redis.keys.return_value = [b"session:1", b"session:2", b"session:3"]

        count = session_store.get_active_session_count()

        assert count == 3
        mock_redis.keys.assert_called_with("session:*")


@pytest.mark.unit
class TestSessionSecurity:
    """Test session security features."""

    def test_session_id_entropy(self, session_store):
        """Test that session IDs have sufficient entropy."""
        session_ids = [session_store.generate_session_id() for _ in range(1000)]

        # Check uniqueness
        assert len(session_ids) == len(set(session_ids))

        # Check character diversity (should use full hex range)
        all_chars = set(''.join(session_ids))
        hex_chars = set('0123456789abcdef')
        assert all_chars == hex_chars

    def test_session_data_isolation(self, session_store, mock_redis):
        """Test that different users' session data is isolated."""
        user1_id = uuid.uuid4()
        user2_id = uuid.uuid4()

        user1_data = {"email": "user1@example.com", "role": "MALL_OPERATOR"}
        user2_data = {"email": "user2@example.com", "role": "TENANT_VIEWER"}

        session1_id = session_store.create_session(user1_id, user1_data)
        session2_id = session_store.create_session(user2_id, user2_data)

        # Session IDs should be different
        assert session1_id != session2_id

        # Each session should have unique key in Redis
        calls = [call[0][0] for call in mock_redis.setex.call_args_list]
        assert len(calls) == 2
        assert calls[0] != calls[1]
