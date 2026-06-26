"""
Pydantic models for the High School Management System API.

This module defines typed request and response models for all endpoints,
replacing untyped Dict[str, Any] responses with structured schemas.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import List, Dict, Any, Optional
from datetime import datetime


class LoginRequest(BaseModel):
    """Request model for login endpoint."""

    username: str = Field(..., min_length=1, max_length=100, description="Teacher username")
    password: str = Field(..., min_length=1, max_length=256, description="Teacher password")


class TokenResponse(BaseModel):
    """JWT token response after successful login."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiry in seconds")
    username: str = Field(..., description="Authenticated username")
    display_name: str = Field(..., description="Teacher display name")
    role: str = Field(..., description="User role (teacher/admin)")


class UserInfo(BaseModel):
    """User information response."""

    username: str
    display_name: str
    role: str


class SignupRequest(BaseModel):
    """Request model for signing up a student to an activity."""

    email: EmailStr = Field(..., description="Student email address")
    teacher_username: Optional[str] = Field(None, description="Deprecated: use Authorization header")


class UnregisterRequest(BaseModel):
    """Request model for unregistering a student from an activity."""

    email: EmailStr = Field(..., description="Student email address")
    teacher_username: Optional[str] = Field(None, description="Deprecated: use Authorization header")


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str = Field(..., description="Response message")


class ErrorResponse(BaseModel):
    """Standardized error response."""

    detail: str = Field(..., description="Error description")
    error_code: Optional[str] = Field(None, description="Machine-readable error code")


class ActivityResponse(BaseModel):
    """Response model for a single activity."""

    description: str = Field(..., description="Activity description")
    schedule: str = Field(..., description="Human-readable schedule")
    schedule_details: Optional[Dict[str, Any]] = Field(None, description="Structured schedule data")
    max_participants: int = Field(..., description="Maximum participants")
    participants: List[str] = Field(default_factory=list, description="List of participant emails")


class ActivityListResponse(BaseModel):
    """Response model for activity list (non-paginated)."""

    activities: Dict[str, ActivityResponse] = Field(..., description="Activities keyed by name")


class PaginatedActivityResponse(BaseModel):
    """Response model for paginated activities."""

    data: List[Dict[str, Any]] = Field(..., description="Page data")
    metadata: Dict[str, Any] = Field(..., description="Pagination metadata")


class TokenData(BaseModel):
    """JWT token payload data."""

    username: str = Field(..., description="Username from token")
    role: str = Field(..., description="User role from token")
    exp: int = Field(..., description="Expiry timestamp")
