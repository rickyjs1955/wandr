"""
Authentication service for password hashing and verification.
"""
from passlib.context import CryptContext
from typing import Optional

# Configure passlib for password hashing with Argon2
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
    argon2__memory_cost=65536,  # 64 MB
    argon2__time_cost=3,         # 3 iterations
    argon2__parallelism=4        # 4 threads
)


def hash_password(password: str) -> str:
    """
    Hash a password using Argon2.

    Args:
        password: Plain text password to hash

    Returns:
        Hashed password string

    Example:
        >>> hashed = hash_password("MySecurePass123!")
        >>> verify_password("MySecurePass123!", hashed)
        True
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Previously hashed password to check against

    Returns:
        True if password matches, False otherwise

    Example:
        >>> hashed = hash_password("MyPassword123!")
        >>> verify_password("MyPassword123!", hashed)
        True
        >>> verify_password("WrongPassword", hashed)
        False
    """
    return pwd_context.verify(plain_password, hashed_password)


def needs_rehash(hashed_password: str) -> bool:
    """
    Check if a hashed password needs to be rehashed (e.g., algorithm updated).

    Args:
        hashed_password: Hashed password to check

    Returns:
        True if password should be rehashed, False otherwise
    """
    return pwd_context.needs_update(hashed_password)


def get_password_strength(password: str) -> dict:
    """
    Evaluate password strength.

    Args:
        password: Plain text password to evaluate

    Returns:
        Dictionary with strength metrics:
        {
            "length": int,
            "has_uppercase": bool,
            "has_lowercase": bool,
            "has_digit": bool,
            "has_special": bool,
            "strength": str  # weak, medium, strong
        }
    """
    import re

    metrics = {
        "length": len(password),
        "has_uppercase": bool(re.search(r'[A-Z]', password)),
        "has_lowercase": bool(re.search(r'[a-z]', password)),
        "has_digit": bool(re.search(r'\d', password)),
        "has_special": bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password)),
    }

    # Calculate strength score
    score = 0
    if metrics["length"] >= 8:
        score += 1
    if metrics["length"] >= 12:
        score += 1
    if metrics["has_uppercase"]:
        score += 1
    if metrics["has_lowercase"]:
        score += 1
    if metrics["has_digit"]:
        score += 1
    if metrics["has_special"]:
        score += 1

    if score <= 3:
        metrics["strength"] = "weak"
    elif score <= 5:
        metrics["strength"] = "medium"
    else:
        metrics["strength"] = "strong"

    return metrics
