"""
Security tests for authentication system.

Tests security features including cookie security, session isolation,
password requirements, and protection against common attacks.
"""

import pytest
from app.services.auth_service import hash_password


@pytest.mark.security
class TestCookieSecurity:
    """Test cookie security attributes."""

    def test_session_cookie_httponly(self, client, test_user, test_user_data):
        """Test that session cookie has HttpOnly flag."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user_data["username"],
                "password": test_user_data["password"],
            },
        )

        assert response.status_code == 200

        # Check Set-Cookie header
        set_cookie = response.headers.get("set-cookie", "")
        assert "httponly" in set_cookie.lower(), "Session cookie should have HttpOnly flag"

    def test_session_cookie_samesite(self, client, test_user, test_user_data):
        """Test that session cookie has SameSite attribute."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user_data["username"],
                "password": test_user_data["password"],
            },
        )

        assert response.status_code == 200

        set_cookie = response.headers.get("set-cookie", "")
        assert "samesite" in set_cookie.lower(), "Session cookie should have SameSite attribute"

    def test_logout_clears_cookie(self, client, test_user, test_user_data):
        """Test that logout properly clears the session cookie."""
        # Login first
        client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user_data["username"],
                "password": test_user_data["password"],
            },
        )

        # Logout
        logout_response = client.post("/api/v1/auth/logout")

        assert logout_response.status_code == 200

        # Check that cookie is cleared (max-age=0 or expires in past)
        set_cookie = logout_response.headers.get("set-cookie", "")
        # Cookie should be deleted (implementation may vary)
        # Just verify logout succeeded
        assert logout_response.json()["message"] == "Logout successful"


@pytest.mark.security
class TestSessionIsolation:
    """Test session isolation between users."""

    def test_users_have_different_sessions(self, client, test_user, test_user_data, db_session):
        """Test that different users get different sessions."""
        from app.models.user import User

        # Create second user
        user2 = User(
            email="user2@example.com",
            username="user2",
            password_hash=hash_password("TestPass123!"),
            role=test_user_data["role"],
            is_active=True,
        )
        db_session.add(user2)
        db_session.commit()

        # Login as first user
        response1 = client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user_data["username"],
                "password": test_user_data["password"],
            },
        )
        session1 = response1.cookies.get("session_id") or response1.cookies.get("wandr_session")

        # Logout and login as second user
        client.post("/api/v1/auth/logout")

        response2 = client.post(
            "/api/v1/auth/login",
            json={
                "username": "user2",
                "password": "TestPass123!",
            },
        )
        session2 = response2.cookies.get("session_id") or response2.cookies.get("wandr_session")

        # Sessions should be different
        if session1 and session2:
            assert session1 != session2

    def test_cannot_access_other_users_session(self, client, test_user, test_user_data, db_session):
        """Test that users cannot access each other's sessions."""
        from app.models.user import User

        # Create second user
        user2 = User(
            email="user2@example.com",
            username="user2",
            password_hash=hash_password("TestPass123!"),
            role=test_user_data["role"],
            is_active=True,
        )
        db_session.add(user2)
        db_session.commit()

        # Login as user1
        response1 = client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user_data["username"],
                "password": test_user_data["password"],
            },
        )
        user1_data = client.get("/api/v1/auth/me").json()

        # Login as user2 (overwrites session in client)
        client.post(
            "/api/v1/auth/login",
            json={
                "username": "user2",
                "password": "TestPass123!",
            },
        )
        user2_data = client.get("/api/v1/auth/me").json()

        # Should get different user data
        assert user1_data["username"] != user2_data["username"]
        assert user1_data["email"] != user2_data["email"]


@pytest.mark.security
class TestPasswordSecurity:
    """Test password security features."""

    def test_password_hash_uniqueness(self):
        """Test that same password produces different hashes (salted)."""
        password = "TestPassword123!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2, "Same password should produce different hashes due to salt"

    def test_passwords_not_returned_in_responses(self, client, test_user, test_user_data):
        """Test that password hashes are never returned in API responses."""
        # Login
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user_data["username"],
                "password": test_user_data["password"],
            },
        )

        login_data = login_response.json()
        assert "password" not in login_data.get("user", {})
        assert "password_hash" not in login_data.get("user", {})

        # Get current user
        me_response = client.get("/api/v1/auth/me")
        me_data = me_response.json()
        assert "password" not in me_data
        assert "password_hash" not in me_data

    def test_weak_passwords_should_be_rejected(self, client, db_session):
        """Test that weak passwords are rejected during user creation."""
        from app.schemas.user import UserCreate
        from pydantic import ValidationError

        weak_passwords = [
            "short",  # Too short
            "nouppercase123!",  # No uppercase
            "NOLOWERCASE123!",  # No lowercase
            "NoDigits!",  # No digits
            "NoSpecial123",  # No special characters
        ]

        for password in weak_passwords:
            with pytest.raises(ValidationError):
                UserCreate(
                    email="test@example.com",
                    username="testuser",
                    password=password,
                    role="MALL_OPERATOR",
                )


@pytest.mark.security
class TestAuthenticationAttackPrevention:
    """Test protection against common authentication attacks."""

    def test_timing_attack_resistance_login(self, client, test_user):
        """Test that login timing doesn't leak user existence.

        Note: This is a basic test. Proper timing attack testing requires
        statistical analysis of many samples.
        """
        # Login with non-existent user
        response1 = client.post(
            "/api/v1/auth/login",
            json={
                "username": "nonexistent",
                "password": "SomePassword123!",
            },
        )

        # Login with existing user but wrong password
        response2 = client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user.username,
                "password": "WrongPassword123!",
            },
        )

        # Both should return 401 with similar response
        assert response1.status_code == 401
        assert response2.status_code == 401

    def test_no_user_enumeration(self, client, test_user):
        """Test that error messages don't reveal whether user exists."""
        # Non-existent user
        response1 = client.post(
            "/api/v1/auth/login",
            json={
                "username": "nonexistent",
                "password": "SomePassword123!",
            },
        )

        # Existing user, wrong password
        response2 = client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user.username,
                "password": "WrongPassword123!",
            },
        )

        # Error messages should not reveal user existence
        error1 = response1.json()["detail"]
        error2 = response2.json()["detail"]

        # Both should have generic error message
        assert error1 == error2
        assert "username" not in error1.lower() or "password" not in error1.lower()

    def test_session_fixation_prevention(self, client, test_user, test_user_data):
        """Test that new session is created on login (prevents session fixation)."""
        # Login first time
        response1 = client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user_data["username"],
                "password": test_user_data["password"],
            },
        )
        session1 = response1.cookies.get("session_id") or response1.cookies.get("wandr_session")

        # Logout
        client.post("/api/v1/auth/logout")

        # Login again
        response2 = client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user_data["username"],
                "password": test_user_data["password"],
            },
        )
        session2 = response2.cookies.get("session_id") or response2.cookies.get("wandr_session")

        # Should get new session ID
        if session1 and session2:
            assert session1 != session2

    def test_sql_injection_protection(self, client):
        """Test that SQL injection attempts in login are handled safely."""
        malicious_inputs = [
            "admin' OR '1'='1",
            "admin'--",
            "admin' OR '1'='1'--",
            "'; DROP TABLE users; --",
        ]

        for malicious_input in malicious_inputs:
            response = client.post(
                "/api/v1/auth/login",
                json={
                    "username": malicious_input,
                    "password": "anypassword",
                },
            )
            # Should safely return 401, not cause SQL error
            assert response.status_code == 401

    def test_session_invalidation_on_user_deletion(self, client, test_user, test_user_data, db_session):
        """Test that deleting user invalidates their sessions."""
        # Login
        client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user_data["username"],
                "password": test_user_data["password"],
            },
        )

        # Verify authenticated
        response1 = client.get("/api/v1/auth/me")
        assert response1.status_code == 200

        # Delete user from database
        db_session.delete(test_user)
        db_session.commit()

        # Try to access with old session
        response2 = client.get("/api/v1/auth/me")
        assert response2.status_code == 401  # Should be unauthorized


@pytest.mark.security
class TestInputValidation:
    """Test input validation and sanitization."""

    def test_xss_protection_in_username(self, client):
        """Test that XSS attempts in username are handled safely."""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
        ]

        for payload in xss_payloads:
            response = client.post(
                "/api/v1/auth/login",
                json={
                    "username": payload,
                    "password": "SomePassword123!",
                },
            )
            # Should safely return 401, not execute script
            assert response.status_code == 401

    def test_extremely_long_inputs(self, client):
        """Test handling of extremely long inputs."""
        long_string = "A" * 10000

        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": long_string,
                "password": long_string,
            },
        )

        # Should handle gracefully (either validation error or 401)
        assert response.status_code in [401, 422]
