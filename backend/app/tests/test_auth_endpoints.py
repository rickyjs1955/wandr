"""
Integration tests for authentication endpoints.

Tests the complete auth flow including login, logout, session management,
and protected route access.
"""

import pytest
from app.models.user import UserRole


@pytest.mark.integration
class TestLoginEndpoint:
    """Test /auth/login endpoint."""

    def test_login_with_valid_username(self, client, test_user, test_user_data):
        """Test login with valid username."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user_data["username"],
                "password": test_user_data["password"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        assert data["user"]["username"] == test_user_data["username"]
        assert data["user"]["email"] == test_user_data["email"]
        assert "password" not in data["user"]
        assert "password_hash" not in data["user"]

        # Check that session cookie was set
        assert "session_id" in response.cookies or "wandr_session" in response.cookies

    def test_login_with_valid_email(self, client, test_user, test_user_data):
        """Test login with valid email instead of username."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user_data["email"],  # Using email as username
                "password": test_user_data["password"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user"]["email"] == test_user_data["email"]

    def test_login_with_wrong_password(self, client, test_user, test_user_data):
        """Test login with incorrect password."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user_data["username"],
                "password": "WrongPassword123!",
            },
        )

        assert response.status_code == 401
        assert "detail" in response.json()

    def test_login_with_nonexistent_user(self, client):
        """Test login with non-existent username."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "nonexistent",
                "password": "SomePassword123!",
            },
        )

        assert response.status_code == 401
        assert "detail" in response.json()

    def test_login_with_inactive_user(self, client, inactive_user):
        """Test login with inactive user account."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": inactive_user.username,
                "password": "TestPass123!",
            },
        )

        assert response.status_code == 403
        assert "inactive" in response.json()["detail"].lower()

    def test_login_with_missing_fields(self, client):
        """Test login with missing required fields."""
        # Missing password
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser"},
        )
        assert response.status_code == 422

        # Missing username
        response = client.post(
            "/api/v1/auth/login",
            json={"password": "TestPass123!"},
        )
        assert response.status_code == 422

        # Empty request
        response = client.post("/api/v1/auth/login", json={})
        assert response.status_code == 422

    def test_login_updates_last_login(self, client, test_user, test_user_data, db_session):
        """Test that login updates the user's last_login timestamp."""
        old_last_login = test_user.last_login

        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user_data["username"],
                "password": test_user_data["password"],
            },
        )

        assert response.status_code == 200

        # Refresh user from database
        db_session.refresh(test_user)
        assert test_user.last_login != old_last_login


@pytest.mark.integration
class TestLogoutEndpoint:
    """Test /auth/logout endpoint."""

    def test_logout_with_valid_session(self, client, test_user, test_user_data):
        """Test logout with a valid session."""
        # First login
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user_data["username"],
                "password": test_user_data["password"],
            },
        )
        assert login_response.status_code == 200

        # Then logout
        logout_response = client.post("/api/v1/auth/logout")
        assert logout_response.status_code == 200
        assert "message" in logout_response.json()

    def test_logout_without_session(self, client):
        """Test logout without an active session."""
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 200  # Should succeed even without session


@pytest.mark.integration
class TestGetCurrentUserEndpoint:
    """Test /auth/me endpoint."""

    def test_get_current_user_with_valid_session(self, client, test_user, test_user_data):
        """Test getting current user with valid session."""
        # Login first
        client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user_data["username"],
                "password": test_user_data["password"],
            },
        )

        # Get current user
        response = client.get("/api/v1/auth/me")

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == test_user_data["username"]
        assert data["email"] == test_user_data["email"]
        assert data["role"] == UserRole.MALL_OPERATOR.value
        assert "password_hash" not in data

    def test_get_current_user_without_session(self, client):
        """Test getting current user without authentication."""
        response = client.get("/api/v1/auth/me")

        assert response.status_code == 401
        assert "detail" in response.json()

    def test_get_current_user_after_logout(self, client, test_user, test_user_data):
        """Test that getting current user fails after logout."""
        # Login
        client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user_data["username"],
                "password": test_user_data["password"],
            },
        )

        # Logout
        client.post("/api/v1/auth/logout")

        # Try to get current user
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401


@pytest.mark.integration
class TestRefreshSessionEndpoint:
    """Test /auth/refresh endpoint."""

    def test_refresh_session_with_valid_session(self, client, test_user, test_user_data):
        """Test refreshing a valid session."""
        # Login first
        client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user_data["username"],
                "password": test_user_data["password"],
            },
        )

        # Refresh session
        response = client.post("/api/v1/auth/refresh")

        assert response.status_code == 200
        assert "message" in response.json()

    def test_refresh_session_without_session(self, client):
        """Test refreshing without an active session."""
        response = client.post("/api/v1/auth/refresh")

        assert response.status_code == 401
        assert "detail" in response.json()


@pytest.mark.integration
class TestAuthHealthEndpoint:
    """Test /auth/health endpoint."""

    def test_auth_health_check(self, client):
        """Test authentication service health check."""
        response = client.get("/api/v1/auth/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "redis_connected" in data


@pytest.mark.integration
class TestProtectedRouteAccess:
    """Test accessing protected routes."""

    def test_access_protected_route_with_valid_session(self, client, test_user, test_user_data):
        """Test that authenticated user can access protected routes."""
        # Login
        client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user_data["username"],
                "password": test_user_data["password"],
            },
        )

        # Access protected endpoint
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 200

    def test_access_protected_route_without_session(self, client):
        """Test that unauthenticated user cannot access protected routes."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401


@pytest.mark.integration
class TestAuthFlow:
    """Test complete authentication flows."""

    def test_complete_login_logout_flow(self, client, test_user, test_user_data):
        """Test complete flow: login -> access protected -> logout -> no access."""
        # Step 1: Login
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user_data["username"],
                "password": test_user_data["password"],
            },
        )
        assert login_response.status_code == 200

        # Step 2: Access protected endpoint
        me_response = client.get("/api/v1/auth/me")
        assert me_response.status_code == 200

        # Step 3: Logout
        logout_response = client.post("/api/v1/auth/logout")
        assert logout_response.status_code == 200

        # Step 4: Try to access protected endpoint
        me_after_logout = client.get("/api/v1/auth/me")
        assert me_after_logout.status_code == 401

    def test_multiple_login_attempts(self, client, test_user, test_user_data):
        """Test multiple login attempts with same user."""
        # First login
        response1 = client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user_data["username"],
                "password": test_user_data["password"],
            },
        )
        assert response1.status_code == 200
        session1 = response1.cookies.get("session_id") or response1.cookies.get("wandr_session")

        # Second login (should create new session)
        response2 = client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user_data["username"],
                "password": test_user_data["password"],
            },
        )
        assert response2.status_code == 200
        session2 = response2.cookies.get("session_id") or response2.cookies.get("wandr_session")

        # Sessions should be different
        if session1 and session2:
            assert session1 != session2

    def test_session_persistence_across_requests(self, client, test_user, test_user_data):
        """Test that session persists across multiple requests."""
        # Login
        client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user_data["username"],
                "password": test_user_data["password"],
            },
        )

        # Make multiple requests
        for _ in range(5):
            response = client.get("/api/v1/auth/me")
            assert response.status_code == 200
            assert response.json()["username"] == test_user_data["username"]
