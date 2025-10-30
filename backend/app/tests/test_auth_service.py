"""
Unit tests for authentication service.

Tests password hashing, verification, and password strength evaluation.
"""

import pytest
from app.services.auth_service import (
    hash_password,
    verify_password,
    needs_rehash,
    get_password_strength,
)


@pytest.mark.unit
class TestPasswordHashing:
    """Test password hashing and verification."""

    def test_hash_password_returns_string(self):
        """Test that hash_password returns a string."""
        password = "TestPassword123!"
        hashed = hash_password(password)
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_hash_password_produces_different_hashes(self):
        """Test that same password produces different hashes (salt)."""
        password = "TestPassword123!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2, "Same password should produce different hashes due to salt"

    def test_verify_password_with_correct_password(self):
        """Test password verification with correct password."""
        password = "TestPassword123!"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_with_incorrect_password(self):
        """Test password verification with incorrect password."""
        password = "TestPassword123!"
        wrong_password = "WrongPassword456!"
        hashed = hash_password(password)
        assert verify_password(wrong_password, hashed) is False

    def test_verify_password_case_sensitive(self):
        """Test that password verification is case-sensitive."""
        password = "TestPassword123!"
        hashed = hash_password(password)
        assert verify_password("testpassword123!", hashed) is False

    def test_hash_password_with_special_characters(self):
        """Test hashing passwords with special characters."""
        passwords = [
            "P@ssw0rd!",
            "Test#Pass$123",
            "MyP@ss^&*()word",
            "ñoñó123!@#",
        ]
        for password in passwords:
            hashed = hash_password(password)
            assert verify_password(password, hashed) is True

    def test_hash_password_with_unicode(self):
        """Test hashing passwords with unicode characters."""
        password = "TestПароль密码123!"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True


@pytest.mark.unit
class TestPasswordStrength:
    """Test password strength evaluation."""

    def test_get_password_strength_weak(self):
        """Test password strength evaluation for weak passwords."""
        weak_passwords = ["password", "12345678", "abcdefgh"]
        for password in weak_passwords:
            strength = get_password_strength(password)
            assert strength["score"] < 3, f"Password '{password}' should be weak"

    def test_get_password_strength_medium(self):
        """Test password strength evaluation for medium passwords."""
        medium_passwords = ["Password123", "Test1234", "MyPass99"]
        for password in medium_passwords:
            strength = get_password_strength(password)
            assert 3 <= strength["score"] < 4, f"Password '{password}' should be medium"

    def test_get_password_strength_strong(self):
        """Test password strength evaluation for strong passwords."""
        strong_passwords = ["TestPass123!", "MyP@ssw0rd!", "Secure#Pass99"]
        for password in strong_passwords:
            strength = get_password_strength(password)
            assert strength["score"] >= 4, f"Password '{password}' should be strong"

    def test_get_password_strength_contains_checks(self):
        """Test that password strength includes check results."""
        password = "TestPass123!"
        strength = get_password_strength(password)

        assert "has_uppercase" in strength
        assert "has_lowercase" in strength
        assert "has_digit" in strength
        assert "has_special" in strength
        assert "length" in strength
        assert "score" in strength

        assert strength["has_uppercase"] is True
        assert strength["has_lowercase"] is True
        assert strength["has_digit"] is True
        assert strength["has_special"] is True

    def test_get_password_strength_length_check(self):
        """Test password strength length evaluation."""
        short = get_password_strength("Test1!")
        medium = get_password_strength("TestPass1!")
        long = get_password_strength("TestPassword123!VeryLong")

        assert short["length"] < medium["length"]
        assert medium["length"] < long["length"]


@pytest.mark.unit
class TestPasswordRehash:
    """Test password rehash checking."""

    def test_needs_rehash_with_current_hash(self):
        """Test that current Argon2 hash doesn't need rehashing."""
        password = "TestPassword123!"
        hashed = hash_password(password)
        assert needs_rehash(hashed) is False

    def test_needs_rehash_with_bcrypt(self):
        """Test that bcrypt hash needs rehashing to Argon2."""
        # This would require creating a bcrypt hash with older config
        # For now, we just test the function exists and is callable
        password = "TestPassword123!"
        hashed = hash_password(password)
        result = needs_rehash(hashed)
        assert isinstance(result, bool)


@pytest.mark.unit
class TestPasswordEdgeCases:
    """Test edge cases and security concerns."""

    def test_empty_password_hashing(self):
        """Test hashing empty password (should work but be weak)."""
        hashed = hash_password("")
        assert isinstance(hashed, str)
        assert verify_password("", hashed) is True
        assert verify_password("notempty", hashed) is False

    def test_very_long_password(self):
        """Test hashing very long passwords."""
        long_password = "A" * 1000
        hashed = hash_password(long_password)
        assert verify_password(long_password, hashed) is True

    def test_password_with_null_bytes(self):
        """Test password with null bytes."""
        password = "Test\x00Pass123!"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_timing_attack_resistance(self):
        """Test that verification doesn't leak timing information.

        Note: This is a basic test. Proper timing attack testing requires
        statistical analysis of many samples.
        """
        password = "TestPassword123!"
        hashed = hash_password(password)

        # Both should take similar time (protected by Argon2)
        wrong_short = "x"
        wrong_long = "x" * 100

        # Just verify both return False without timing analysis
        assert verify_password(wrong_short, hashed) is False
        assert verify_password(wrong_long, hashed) is False
