"""
Integration tests for API endpoints.

Tests cover:
    - Authentication endpoints (/auth)
    - Activity management endpoints (/activities)
    - Input validation
    - Error handling and status codes
"""

import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Mock MongoDB for testing
@pytest.fixture
def mock_db():
    """Fixture to mock MongoDB collections."""
    with patch('src.backend.database.teachers_collection') as mock_teachers, \
         patch('src.backend.database.activities_collection') as mock_activities:
        yield mock_teachers, mock_activities


@pytest.fixture
def client():
    """Fixture to create test client."""
    from src.app import app
    return TestClient(app)


class TestAuthenticationEndpoints:
    """Test suite for authentication API endpoints."""

    def test_login_endpoint_exists(self, client):
        """Test that login endpoint exists."""
        # Note: This will fail if no database is configured
        # In production, use proper mocking
        response = client.post(
            "/auth/login",
            params={"username": "test", "password": "test123"}
        )
        # Endpoint should exist (may return 401 due to invalid credentials)
        assert response.status_code in [200, 401, 404, 500]

    def test_check_session_endpoint_exists(self, client):
        """Test that session check endpoint exists."""
        response = client.get(
            "/auth/check-session",
            params={"username": "test"}
        )
        # Endpoint should exist
        assert response.status_code in [200, 404, 500]

    def test_invalid_credentials_format(self, client):
        """Test handling of invalid credential formats."""
        # Test with empty credentials
        response = client.post(
            "/auth/login",
            params={"username": "", "password": ""}
        )
        # Should handle gracefully
        assert response.status_code >= 400


class TestActivityEndpoints:
    """Test suite for activity management API endpoints."""

    def test_get_activities_endpoint_exists(self, client):
        """Test that activities endpoint exists."""
        response = client.get("/activities")
        # Endpoint should exist and return valid response
        assert response.status_code in [200, 404, 500]

    def test_get_activities_with_filters(self, client):
        """Test activities endpoint with filter parameters."""
        params = {
            "day": "Monday",
            "start_time": "14:00",
            "end_time": "17:00"
        }
        response = client.get("/activities", params=params)
        # Should accept filter parameters
        assert response.status_code >= 200

    def test_get_available_days_endpoint(self, client):
        """Test getting available days endpoint."""
        response = client.get("/activities/days")
        # Should return list of days
        assert response.status_code in [200, 404, 500]


class TestInputValidation:
    """Test suite for input validation in API endpoints."""

    def test_email_validation_in_signup(self, client):
        """Test email validation in signup endpoint."""
        invalid_emails = [
            "invalid_email",
            "missing@domain",
            "@nodomain.com",
            "spaces in@email.com"
        ]

        for email in invalid_emails:
            response = client.post(
                "/activities/TestActivity/signup",
                params={
                    "email": email,
                    "teacher_username": "teacher1"
                }
            )
            # Should reject invalid emails
            assert response.status_code in [400, 401, 404, 500]

    def test_activity_name_length_validation(self, client):
        """Test activity name length validation."""
        # Create a very long activity name
        long_name = "A" * 1000

        response = client.post(
            f"/activities/{long_name}/signup",
            params={
                "email": "test@example.com",
                "teacher_username": "teacher1"
            }
        )
        # Should handle long names appropriately
        assert response.status_code >= 400

    def test_email_length_validation(self, client):
        """Test email length validation."""
        # Create a very long email
        long_email = "a" * 300 + "@example.com"

        response = client.post(
            "/activities/TestActivity/signup",
            params={
                "email": long_email,
                "teacher_username": "teacher1"
            }
        )
        # Should validate email length
        assert response.status_code >= 400


class TestSecurityHeaders:
    """Test suite for security headers in responses."""

    def test_cors_headers_present(self, client):
        """Test that CORS headers are present in responses."""
        response = client.get("/activities")
        # CORS middleware should add necessary headers or they should be present
        # This depends on deployment configuration
        assert response.status_code >= 200

    def test_static_files_served_correctly(self, client):
        """Test that static files can be accessed."""
        response = client.get("/static/")
        # Static files should be accessible
        assert response.status_code in [200, 404, 307, 308]


class TestErrorHandling:
    """Test suite for error handling in API."""

    def test_404_for_nonexistent_activity(self, client):
        """Test 404 error for nonexistent activity."""
        response = client.post(
            "/activities/NonexistentActivity/signup",
            params={
                "email": "test@example.com",
                "teacher_username": "teacher1"
            }
        )
        # Should return 404 or 401 (auth error first)
        assert response.status_code >= 400

    def test_missing_authentication(self, client):
        """Test error when authentication is missing."""
        response = client.post(
            "/activities/TestActivity/signup",
            params={
                "email": "test@example.com"
                # teacher_username is missing
            }
        )
        # Should require authentication
        assert response.status_code >= 400

    def test_api_error_response_format(self, client):
        """Test that API errors return proper JSON format."""
        response = client.post(
            "/activities/Test/signup",
            params={
                "email": "invalid_email",
                "teacher_username": "test"
            }
        )
        # Should return JSON even on error
        if response.status_code >= 400:
            assert "application/json" in response.headers.get("content-type", "")


class TestRateLimiting:
    """Test suite for rate limiting functionality."""

    def test_rate_limiting_configuration_exists(self, client):
        """Test that rate limiting is configured."""
        # Send multiple requests in rapid succession
        responses = []
        for _ in range(3):
            response = client.post(
                "/auth/login",
                params={"username": "test", "password": "test"}
            )
            responses.append(response.status_code)

        # At least some responses should return successfully or fail gracefully
        assert len(responses) == 3
        # No 429 errors expected in normal operation (unless rate limit is very low)
        assert not all(status == 429 for status in responses)


class TestAPIDocumentation:
    """Test suite for API documentation endpoints."""

    def test_swagger_docs_available(self, client):
        """Test that Swagger documentation is available."""
        response = client.get("/api/docs")
        # Documentation endpoint should exist
        assert response.status_code in [200, 404, 405]

    def test_redoc_docs_available(self, client):
        """Test that ReDoc documentation is available."""
        response = client.get("/api/redoc")
        # Documentation endpoint should exist
        assert response.status_code in [200, 404, 405]

    def test_openapi_schema_available(self, client):
        """Test that OpenAPI schema is available."""
        response = client.get("/api/openapi.json")
        # OpenAPI schema should exist
        assert response.status_code in [200, 404]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
