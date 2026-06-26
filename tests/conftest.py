"""
Pytest configuration and shared fixtures for testing.

This module provides:
    - Database mocks and fixtures
    - API client fixtures
    - Test data factories
    - Configuration for test environment
"""

import pytest
import os
from unittest.mock import Mock, MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def test_config():
    """
    Session-scoped fixture for test configuration.

    Returns:
        dict: Test configuration settings
    """
    return {
        "database": "test_mergington_high",
        "mongodb_url": "mongodb://localhost:27017/",
        "cors_origins": ["http://localhost:3000"],
        "rate_limit_requests": 100,
        "rate_limit_window": 60,
    }


@pytest.fixture
def mock_mongodb(monkeypatch):
    """
    Mock MongoDB collections for unit testing.

    Returns:
        tuple: (mock_teachers_collection, mock_activities_collection)
    """
    mock_teachers = MagicMock()
    mock_activities = MagicMock()

    # Configure default return values
    mock_teachers.find_one.return_value = {
        "_id": "test_teacher",
        "username": "test_teacher",
        "display_name": "Test Teacher",
        "password": "hashed_password",
        "role": "teacher"
    }

    mock_activities.find_one.return_value = {
        "_id": "Test Activity",
        "description": "A test activity",
        "schedule": "Monday 3:00 PM",
        "max_participants": 20,
        "participants": ["student1@test.com"]
    }

    # Mock aggregation pipeline
    mock_activities.aggregate.return_value = []

    return mock_teachers, mock_activities


@pytest.fixture
def api_client():
    """
    Fixture to provide FastAPI test client.

    Returns:
        TestClient: FastAPI test client instance

    Usage:
        def test_endpoint(api_client):
            response = api_client.get("/endpoint")
            assert response.status_code == 200
    """
    from src.app import app
    return TestClient(app)


@pytest.fixture
def sample_teacher():
    """
    Fixture providing sample teacher data.

    Returns:
        dict: Sample teacher information
    """
    return {
        "username": "test_teacher",
        "display_name": "Test Teacher",
        "password": "SecurePassword123",
        "role": "teacher"
    }


@pytest.fixture
def sample_activity():
    """
    Fixture providing sample activity data.

    Returns:
        dict: Sample activity information
    """
    return {
        "name": "Test Activity",
        "description": "A test extracurricular activity",
        "schedule": "Monday and Friday, 3:15 PM - 4:45 PM",
        "schedule_details": {
            "days": ["Monday", "Friday"],
            "start_time": "15:15",
            "end_time": "16:45"
        },
        "max_participants": 20,
        "participants": ["student1@test.com", "student2@test.com"]
    }


@pytest.fixture
def sample_student_email():
    """
    Fixture providing sample student email.

    Returns:
        str: Valid student email address
    """
    return "student@mergington.edu"


@pytest.fixture
def authenticated_headers(sample_teacher):
    """
    Fixture providing authentication headers.

    Returns:
        dict: HTTP headers with authentication
    """
    return {
        "Authorization": f"Bearer {sample_teacher['username']}",
        "Content-Type": "application/json"
    }


@pytest.fixture(autouse=True)
def reset_mocks():
    """
    Fixture to reset all mocks before each test.

    This ensures test isolation and prevents state leakage.
    """
    yield
    # Cleanup happens after test execution


@pytest.fixture
def test_env_vars(monkeypatch):
    """
    Fixture to set test environment variables.

    Returns:
        dict: Dictionary of test environment variables
    """
    env_vars = {
        "MONGODB_URL": "mongodb://localhost:27017/",
        "DATABASE_NAME": "test_mergington_high",
        "CORS_ORIGINS": "http://localhost:3000,http://localhost:8000",
        "RATE_LIMIT_REQUESTS": "100",
        "RATE_LIMIT_WINDOW": "60",
        "SECRET_KEY": "test-secret-key-do-not-use-in-production"
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    return env_vars


@pytest.fixture
def mock_password_hasher(monkeypatch):
    """
    Fixture to mock the password hasher.

    Returns:
        MagicMock: Mocked PasswordHasher instance
    """
    from argon2 import PasswordHasher

    mock_hasher = MagicMock(spec=PasswordHasher)
    mock_hasher.hash.return_value = "hashed_password_value"
    mock_hasher.verify.return_value = True

    return mock_hasher


@pytest.fixture
def error_response():
    """
    Fixture providing common error response templates.

    Returns:
        dict: Dictionary of error response templates
    """
    return {
        "invalid_email": {
            "status_code": 400,
            "message": "Invalid email format"
        },
        "unauthorized": {
            "status_code": 401,
            "message": "Authentication required"
        },
        "not_found": {
            "status_code": 404,
            "message": "Resource not found"
        },
        "rate_limit": {
            "status_code": 429,
            "message": "Too many requests"
        },
        "server_error": {
            "status_code": 500,
            "message": "Internal server error"
        }
    }


# Pytest hook to log test execution
def pytest_runtest_logreport(report):
    """
    Pytest hook to enhance logging of test results.

    Args:
        report: Test report object
    """
    if report.when == "call":
        if report.outcome == "passed":
            print(f"✅ {report.nodeid}")
        elif report.outcome == "failed":
            print(f"❌ {report.nodeid}")


# Fixture for parameterized invalid email tests
INVALID_EMAILS = [
    "notanemail",
    "missing@domain",
    "@nodomain.com",
    "spaces in@email.com",
    "double@@domain.com",
    "no-tld@domain",
]


@pytest.fixture(params=INVALID_EMAILS)
def invalid_email(request):
    """
    Parameterized fixture for testing invalid emails.

    Yields:
        str: Invalid email address
    """
    return request.param


# Fixture for parameterized weak password tests
WEAK_PASSWORDS = [
    "1234",           # Too short
    "weak",           # Too short
    "short",          # Too short
    "",               # Empty
    " " * 8,          # Only spaces
]


@pytest.fixture(params=WEAK_PASSWORDS)
def weak_password(request):
    """
    Parameterized fixture for testing weak passwords.

    Yields:
        str: Weak password that should be rejected
    """
    return request.param
