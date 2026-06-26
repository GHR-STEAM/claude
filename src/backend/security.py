"""
Security utilities and middleware for the High School Management System API.

This module provides:
    - Rate limiting configuration to prevent brute force attacks
    - Request validation utilities
    - Security decorators and handlers

Configuration:
    Rate limiting settings are configured via environment variables:
    - RATE_LIMIT_REQUESTS: Number of allowed requests (default: 100)
    - RATE_LIMIT_WINDOW: Time window in seconds (default: 60)

Example:
    >>> from security import limiter, get_rate_limit_string
    >>> @router.post("/login")
    ... @limiter.limit(get_rate_limit_string())
    ... def login(username: str, password: str):
    ...     # Protected endpoint with rate limiting
    ...     pass
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import HTTPException, Request
import os
from typing import Optional

# Initialize rate limiter with remote address as key function
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"]  # Default limit: 100 requests per minute
)

# Get rate limit settings from environment
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

# Security thresholds
MAX_LOGIN_ATTEMPTS = 5
MAX_REGISTRATION_ATTEMPTS = 3
MAX_PASSWORD_LENGTH = 256
MIN_PASSWORD_LENGTH = 8


def get_rate_limit_string() -> str:
    """
    Get the rate limit string for slowapi decorator.

    Returns:
        str: Rate limit string in format "requests/window_seconds" (e.g., "100/60seconds")

    Example:
        >>> rate_limit = get_rate_limit_string()
        >>> print(rate_limit)
        '100/60seconds'
    """
    return f"{RATE_LIMIT_REQUESTS}/{RATE_LIMIT_WINDOW}seconds"


def handle_rate_limit_exceeded(request: Request, exc: RateLimitExceeded) -> HTTPException:
    """
    Custom handler for rate limit exceeded errors.

    Args:
        request: The incoming request object
        exc: The RateLimitExceeded exception

    Returns:
        HTTPException: HTTP 429 (Too Many Requests) with descriptive message

    Raises:
        HTTPException: Always raises with status 429
    """
    raise HTTPException(
        status_code=429,
        detail="Too many requests. Please try again later. Your IP has been temporarily rate-limited."
    )


def validate_password_strength(password: str) -> bool:
    """
    Validate password meets minimum security requirements.

    Args:
        password: The password to validate

    Returns:
        bool: True if password is valid, False otherwise

    Password Requirements:
        - Minimum length: 8 characters
        - Maximum length: 256 characters
        - Must not be empty or None

    Example:
        >>> validate_password_strength("SecurePassword123!")
        True
        >>> validate_password_strength("weak")
        False
    """
    if not password or not isinstance(password, str):
        return False

    length = len(password)
    return MIN_PASSWORD_LENGTH <= length <= MAX_PASSWORD_LENGTH


def get_client_ip(request: Request) -> str:
    """
    Extract client IP address from request, accounting for proxies.

    Args:
        request: The incoming request object

    Returns:
        str: Client IP address

    Note:
        This function checks X-Forwarded-For header for proxy situations
        before falling back to the direct connection IP.

    Example:
        >>> ip = get_client_ip(request)
        >>> print(ip)
        '192.168.1.1'
    """
    if request.headers.get("x-forwarded-for"):
        return request.headers["x-forwarded-for"].split(",")[0].strip()
    return request.client.host if request.client else "unknown"
