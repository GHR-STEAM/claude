"""
Endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException, Query, Request, Depends
from fastapi.responses import RedirectResponse
from typing import Dict, Any, Optional, List
from pydantic import EmailStr
import re

from ..database import activities_collection, teachers_collection
from ..security import limiter, get_rate_limit_string
from ..pagination import PaginationHelper
from ..cache_invalidation import invalidate_activities_cache
from ..auth import get_current_user
from ..audit import log_action
from ..models import UserInfo, SignupRequest, UnregisterRequest, MessageResponse

router = APIRouter(
    prefix="/activities",
    tags=["activities"]
)

EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
MAX_STRING_LENGTH = 500  # Prevent very long inputs
MAX_EMAIL_LENGTH = 254  # RFC 5321

def validate_email(email: str) -> bool:
    """Validate email format with length check"""
    if not email or len(email) > MAX_EMAIL_LENGTH:
        return False
    return EMAIL_PATTERN.match(email) is not None

def validate_input_length(value: str, max_length: int = MAX_STRING_LENGTH) -> bool:
    """Validate input length to prevent DoS"""
    return value is not None and len(value) <= max_length

@router.get("", response_model=Dict[str, Any])
@router.get("/", response_model=Dict[str, Any])
def get_activities(
    day: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    skip: int = Query(0, ge=0, description="Number of activities to skip for pagination"),
    limit: int = Query(0, ge=0, le=PaginationHelper.MAX_PAGE_SIZE, description="Max activities to return (0 = all)"),
) -> Dict[str, Any]:
    """
    Get all activities with their details, with optional filtering by day and time.

    Supports cursor-based pagination via skip/limit parameters.
    When limit=0 (default), all matching activities are returned as a dict keyed by name.
    When limit>0, a paginated response with data and metadata is returned.

    - day: Filter activities occurring on this day (e.g., 'Monday', 'Tuesday')
    - start_time: Filter activities starting at or after this time (24-hour format, e.g., '14:30')
    - end_time: Filter activities ending at or before this time (24-hour format, e.g., '17:00')
    - skip: Number of activities to skip (for pagination)
    - limit: Maximum number of activities to return (0 = all, max 100)
    """
    # Build the query based on provided filters
    query = {}

    if day:
        query["schedule_details.days"] = {"$in": [day]}

    if start_time:
        query["schedule_details.start_time"] = {"$gte": start_time}

    if end_time:
        query["schedule_details.end_time"] = {"$lte": end_time}

    # Paginated response when limit is specified
    if limit > 0:
        response = PaginationHelper.paginate_query(
            collection=activities_collection,
            query=query,
            skip=skip,
            limit=limit,
            sort_field="_id",
        )
        return {
            "data": response.data,
            "metadata": response.metadata.dict(),
        }

    # Default: return all activities as dict keyed by name (backward compatible)
    activities = {}
    for activity in activities_collection.find(query):
        name = activity.pop('_id')
        activities[name] = activity

    return activities

@router.get("/days", response_model=List[str])
def get_available_days() -> List[str]:
    """Get a list of all days that have activities scheduled"""
    # Aggregate to get unique days across all activities
    pipeline = [
        {"$unwind": "$schedule_details.days"},
        {"$group": {"_id": "$schedule_details.days"}},
        {"$sort": {"_id": 1}}  # Sort days alphabetically
    ]
    
    days = []
    for day_doc in activities_collection.aggregate(pipeline):
        days.append(day_doc["_id"])
    
    return days

@router.post("/{activity_name}/signup", response_model=MessageResponse)
@limiter.limit(get_rate_limit_string())
def signup_for_activity(
    request: Request,
    activity_name: str,
    body: SignupRequest,
    current_user: UserInfo = Depends(get_current_user),
) -> MessageResponse:
    """
    Sign up a student for an activity.

    Requires JWT authentication. Rate limited to prevent abuse.

    Args:
        request: The incoming request object (required for rate limiting)
        activity_name: Name of the activity to sign up for
        body: SignupRequest with student email
        current_user: Authenticated teacher from JWT

    Returns:
        MessageResponse: Confirmation message

    Raises:
        HTTPException: 400 for invalid input, 404 if activity not found
    """
    email = str(body.email)

    if not validate_input_length(activity_name):
        raise HTTPException(status_code=400, detail="Activity name is too long")

    if not validate_email(email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    # Get the activity
    activity = activities_collection.find_one({"_id": activity_name})
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Validate student is not already signed up
    if email in activity["participants"]:
        raise HTTPException(
            status_code=400, detail="Already signed up for this activity"
        )

    # Add student to participants
    result = activities_collection.update_one(
        {"_id": activity_name},
        {"$push": {"participants": email}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=500, detail="Failed to update activity")

    invalidate_activities_cache()
    log_action("signup", current_user.username, {"activity": activity_name, "email": email})
    return MessageResponse(message=f"Signed up {email} for {activity_name}")

@router.post("/{activity_name}/unregister", response_model=MessageResponse)
@limiter.limit(get_rate_limit_string())
def unregister_from_activity(
    request: Request,
    activity_name: str,
    body: UnregisterRequest,
    current_user: UserInfo = Depends(get_current_user),
) -> MessageResponse:
    """
    Remove a student from an activity.

    Requires JWT authentication. Rate limited to prevent abuse.

    Args:
        request: The incoming request object (required for rate limiting)
        activity_name: Name of the activity to unregister from
        body: UnregisterRequest with student email
        current_user: Authenticated teacher from JWT

    Returns:
        MessageResponse: Confirmation message

    Raises:
        HTTPException: 400 for invalid input, 404 if activity not found
    """
    email = str(body.email)

    if not validate_input_length(activity_name):
        raise HTTPException(status_code=400, detail="Activity name is too long")

    if not validate_email(email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    # Get the activity
    activity = activities_collection.find_one({"_id": activity_name})
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Validate student is signed up
    if email not in activity["participants"]:
        raise HTTPException(
            status_code=400, detail="Not registered for this activity"
        )

    # Remove student from participants
    result = activities_collection.update_one(
        {"_id": activity_name},
        {"$pull": {"participants": email}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=500, detail="Failed to update activity")

    invalidate_activities_cache()
    log_action("unregister", current_user.username, {"activity": activity_name, "email": email})
    return MessageResponse(message=f"Unregistered {email} from {activity_name}")