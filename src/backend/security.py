"""
Security utilities for the High School Management System API
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import HTTPException
import os

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Get rate limit settings from environment
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

def get_rate_limit_string() -> str:
    """Get the rate limit string for slowapi"""
    return f"{RATE_LIMIT_REQUESTS}/{RATE_LIMIT_WINDOW}seconds"

def handle_rate_limit_exceeded(request, exc):
    """Custom handler for rate limit exceeded"""
    raise HTTPException(
        status_code=429,
        detail="Too many requests. Please try again later."
    )
