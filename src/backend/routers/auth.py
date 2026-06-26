"""
Authentication endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
import os

from ..database import teachers_collection
from ..security import limiter, get_rate_limit_string

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

ph = PasswordHasher()

@router.post("/login")
@limiter.limit(get_rate_limit_string())
def login(request: Request, username: str, password: str) -> Dict[str, Any]:
    """
    Login a teacher account.

    Args:
        request: The incoming request object (required for rate limiting)
        username: Teacher username
        password: Teacher password

    Returns:
        dict: Teacher information including username, display_name, and role

    Raises:
        HTTPException: 401 if credentials are invalid
    """
    # Find the teacher in the database
    teacher = teachers_collection.find_one({"_id": username})

    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Verify password using Argon2
    try:
        ph.verify(teacher["password"], password)
    except (VerifyMismatchError, InvalidHashError):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Return teacher information (excluding password)
    return {
        "username": teacher["username"],
        "display_name": teacher["display_name"],
        "role": teacher["role"]
    }

@router.get("/check-session")
def check_session(username: str) -> Dict[str, Any]:
    """Check if a session is valid by username"""
    teacher = teachers_collection.find_one({"_id": username})
    
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    
    return {
        "username": teacher["username"],
        "display_name": teacher["display_name"],
        "role": teacher["role"]
    }