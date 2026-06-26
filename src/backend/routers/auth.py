"""
Authentication endpoints for the High School Management System API.

Provides JWT-based login and session validation.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, Any
import logging

from ..database import teachers_collection
from ..security import limiter, get_rate_limit_string
from ..auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from ..models import LoginRequest, TokenResponse, UserInfo, MessageResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(get_rate_limit_string())
def login(request: Dict[str, Any], credentials: LoginRequest) -> TokenResponse:
    """
    Login a teacher account and receive a JWT access token.

    Args:
        credentials: LoginRequest body with username and password

    Returns:
        TokenResponse: JWT token with user info

    Raises:
        HTTPException: 401 if credentials are invalid
    """
    teacher = authenticate_user(credentials.username, credentials.password)

    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(teacher["username"], teacher["role"])

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        username=teacher["username"],
        display_name=teacher["display_name"],
        role=teacher["role"],
    )


@router.get("/check-session", response_model=UserInfo)
def check_session(user: UserInfo = Depends(get_current_user)) -> UserInfo:
    """
    Validate the current session via JWT token.

    Returns:
        UserInfo: Authenticated user information

    Raises:
        HTTPException: 401 if token is invalid or expired
    """
    return user


@router.get("/me", response_model=UserInfo)
def get_me(user: UserInfo = Depends(get_current_user)) -> UserInfo:
    """
    Get the current authenticated user's info.

    Returns:
        UserInfo: Current user information
    """
    return user