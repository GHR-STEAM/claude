"""
JWT authentication system for the High School Management System API.

This module provides:
    - JWT token creation and verification
    - Password hashing and verification (Argon2)
    - get_current_user dependency for protected endpoints
    - Token-based session validation

Usage:
    >>> from auth import get_current_user, create_access_token
    >>> @router.post("/protected")
    ... def protected(user = Depends(get_current_user)):
    ...     return {"user": user.username}
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional
import logging

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

from .database import teachers_collection
from .models import TokenData, TokenResponse, UserInfo

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE-ME-IN-PRODUCTION-USE-A-LONG-RANDOM-KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

_password_hasher = PasswordHasher()
_security = HTTPBearer(auto_error=True)


def hash_password(password: str) -> str:
    """Hash a password using Argon2.

    Args:
        password: Plain text password

    Returns:
        str: Argon2 hash
    """
    return _password_hasher.hash(password)


def verify_password(hashed_password: str, plain_password: str) -> bool:
    """Verify a password against its Argon2 hash.

    Args:
        hashed_password: Stored Argon2 hash
        plain_password: Plain text password to verify

    Returns:
        bool: True if password matches
    """
    try:
        _password_hasher.verify(hashed_password, plain_password)
        return True
    except (VerifyMismatchError, InvalidHashError):
        return False
    except Exception:
        return False


def create_access_token(username: str, role: str) -> str:
    """Create a JWT access token.

    Args:
        username: The authenticated user's username
        role: The user's role (teacher/admin)

    Returns:
        str: Encoded JWT token
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "username": username,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> TokenData:
    """Decode and validate a JWT access token.

    Args:
        token: JWT token string

    Returns:
        TokenData: Decoded token payload

    Raises:
        HTTPException: 401 if token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return TokenData(
            username=payload["username"],
            role=payload["role"],
            exp=payload["exp"],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """Authenticate a user by username and password.

    Args:
        username: Teacher username
        password: Plain text password

    Returns:
        dict or None: Teacher document if authenticated, None otherwise
    """
    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        return None

    if not verify_password(teacher["password"], password):
        return None

    return teacher


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> UserInfo:
    """FastAPI dependency to get the current authenticated user from JWT.

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        UserInfo: Authenticated user information

    Raises:
        HTTPException: 401 if token is invalid or user not found
    """
    token_data = decode_access_token(credentials.credentials)

    teacher = teachers_collection.find_one({"_id": token_data.username})
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return UserInfo(
        username=teacher["username"],
        display_name=teacher["display_name"],
        role=teacher["role"],
    )


def require_role(role: str):
    """Dependency factory to require a specific role.

    Args:
        role: Required role (e.g., "admin")

    Returns:
        Dependency function that checks the user's role

    Example:
        >>> @router.delete("/admin/endpoint")
        ... def admin_endpoint(user = Depends(require_role("admin"))):
        ...     pass
    """
    def role_checker(user: UserInfo = Depends(get_current_user)) -> UserInfo:
        if user.role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {role} role",
            )
        return user

    return role_checker
