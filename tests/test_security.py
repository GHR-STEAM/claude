"""
Unit tests for security utilities and middleware.

Tests cover:
    - Rate limiting configuration
    - Password strength validation
    - Client IP extraction
    - Rate limit error handling
"""

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

# Import security functions
from src.backend.security import (
    get_rate_limit_string,
    validate_password_strength,
    get_client_ip,
    handle_rate_limit_exceeded,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW,
)


class TestRateLimiting:
    """Test suite for rate limiting functionality."""

    def test_get_rate_limit_string_format(self):
        """Test that rate limit string is formatted correctly."""
        rate_limit = get_rate_limit_string()
        assert isinstance(rate_limit, str)
        assert "seconds" in rate_limit
        assert "/" in rate_limit

    def test_get_rate_limit_string_values(self):
        """Test that rate limit string contains correct values."""
        rate_limit = get_rate_limit_string()
        expected = f"{RATE_LIMIT_REQUESTS}/{RATE_LIMIT_WINDOW}seconds"
        assert rate_limit == expected

    def test_rate_limit_configuration(self):
        """Test that rate limit configuration is loaded from environment."""
        assert RATE_LIMIT_REQUESTS > 0
        assert RATE_LIMIT_WINDOW > 0
        assert isinstance(RATE_LIMIT_REQUESTS, int)
        assert isinstance(RATE_LIMIT_WINDOW, int)


class TestPasswordValidation:
    """Test suite for password strength validation."""

    def test_valid_password(self):
        """Test that valid password passes validation."""
        assert validate_password_strength("SecurePassword123!") is True
        assert validate_password_strength("ValidPassword@2024") is True
        assert validate_password_strength("12345678") is True  # Min length

    def test_weak_password_too_short(self):
        """Test that passwords shorter than minimum length are rejected."""
        assert validate_password_strength("weak") is False
        assert validate_password_strength("short") is False
        assert validate_password_strength("1234567") is False  # 7 chars, min is 8

    def test_password_empty_or_none(self):
        """Test that empty or None passwords are rejected."""
        assert validate_password_strength("") is False
        assert validate_password_strength(None) is False

    def test_password_too_long(self):
        """Test that excessively long passwords are rejected."""
        long_password = "a" * 257  # Exceeds MAX_PASSWORD_LENGTH
        assert validate_password_strength(long_password) is False

    def test_password_at_boundaries(self):
        """Test passwords at minimum and maximum length boundaries."""
        min_password = "12345678"  # Exactly 8 characters
        max_password = "a" * 256  # Exactly 256 characters

        assert validate_password_strength(min_password) is True
        assert validate_password_strength(max_password) is True

    def test_password_non_string_type(self):
        """Test that non-string password inputs are rejected."""
        assert validate_password_strength(12345678) is False
        assert validate_password_strength([]) is False
        assert validate_password_strength({}) is False


class TestClientIPExtraction:
    """Test suite for client IP address extraction."""

    def test_get_client_ip_direct_connection(self):
        """Test IP extraction from direct connection."""
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "192.168.1.1"
        request.headers = {}

        ip = get_client_ip(request)
        assert ip == "192.168.1.1"

    def test_get_client_ip_with_proxy(self):
        """Test IP extraction from X-Forwarded-For header (proxy)."""
        request = Mock(spec=Request)
        request.headers = {"x-forwarded-for": "203.0.113.45, 198.51.100.178"}
        request.client = Mock()
        request.client.host = "198.51.100.178"

        ip = get_client_ip(request)
        assert ip == "203.0.113.45"  # Should get the leftmost IP

    def test_get_client_ip_proxy_with_spaces(self):
        """Test IP extraction from X-Forwarded-For with extra spaces."""
        request = Mock(spec=Request)
        request.headers = {"x-forwarded-for": "  203.0.113.45  ,  198.51.100.178  "}
        request.client = Mock()
        request.client.host = "198.51.100.178"

        ip = get_client_ip(request)
        assert ip == "203.0.113.45"  # Should strip spaces

    def test_get_client_ip_no_client(self):
        """Test IP extraction when client is None."""
        request = Mock(spec=Request)
        request.client = None
        request.headers = {}

        ip = get_client_ip(request)
        assert ip == "unknown"

    def test_get_client_ip_single_proxy(self):
        """Test IP extraction from single IP in X-Forwarded-For."""
        request = Mock(spec=Request)
        request.headers = {"x-forwarded-for": "203.0.113.45"}
        request.client = Mock()
        request.client.host = "198.51.100.178"

        ip = get_client_ip(request)
        assert ip == "203.0.113.45"


class TestErrorHandling:
    """Test suite for error handling and exceptions."""

    def test_handle_rate_limit_exceeded(self):
        """Test that rate limit handler raises appropriate exception."""
        from slowapi.errors import RateLimitExceeded

        request = Mock(spec=Request)
        exc = RateLimitExceeded("100 per 60 seconds")

        with pytest.raises(Exception) as exc_info:
            handle_rate_limit_exceeded(request, exc)

        # Check that HTTPException is raised with correct status code
        assert exc_info.value.status_code == 429

    def test_rate_limit_error_message(self):
        """Test that rate limit error has descriptive message."""
        from slowapi.errors import RateLimitExceeded

        request = Mock(spec=Request)
        exc = RateLimitExceeded("100 per 60 seconds")

        with pytest.raises(Exception) as exc_info:
            handle_rate_limit_exceeded(request, exc)

        assert "Too many requests" in str(exc_info.value.detail)
        assert "rate-limited" in str(exc_info.value.detail).lower()


class TestSecurityConfiguration:
    """Test suite for security configuration constants."""

    def test_minimum_password_length(self):
        """Test that minimum password length is reasonable."""
        from src.backend.security import MIN_PASSWORD_LENGTH
        assert MIN_PASSWORD_LENGTH >= 8
        assert MIN_PASSWORD_LENGTH <= 16

    def test_maximum_password_length(self):
        """Test that maximum password length is reasonable."""
        from src.backend.security import MAX_PASSWORD_LENGTH
        assert MAX_PASSWORD_LENGTH >= 256
        assert MAX_PASSWORD_LENGTH <= 1024

    def test_security_thresholds(self):
        """Test that security thresholds are properly set."""
        from src.backend.security import MAX_LOGIN_ATTEMPTS, MAX_REGISTRATION_ATTEMPTS
        assert MAX_LOGIN_ATTEMPTS > 0
        assert MAX_REGISTRATION_ATTEMPTS > 0
        assert MAX_LOGIN_ATTEMPTS >= MAX_REGISTRATION_ATTEMPTS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
