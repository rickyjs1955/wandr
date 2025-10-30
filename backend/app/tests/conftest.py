"""
Pytest configuration and fixtures for testing.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.user import User, UserRole
from app.services.auth_service import hash_password

# Use in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a new database session for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with database session override."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user_data():
    """Sample user data for testing."""
    return {
        "email": "test@example.com",
        "username": "testuser",
        "password": "TestPass123!",
        "role": UserRole.MALL_OPERATOR,
    }


@pytest.fixture
def test_user(db_session, test_user_data):
    """Create a test user in the database."""
    user = User(
        email=test_user_data["email"],
        username=test_user_data["username"],
        password_hash=hash_password(test_user_data["password"]),
        role=test_user_data["role"],
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def inactive_user(db_session):
    """Create an inactive test user."""
    user = User(
        email="inactive@example.com",
        username="inactiveuser",
        password_hash=hash_password("TestPass123!"),
        role=UserRole.MALL_OPERATOR,
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
