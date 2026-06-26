"""
Audit logging for the High School Management System API.

This module provides:
    - Audit log recording for mutation operations
    - Audit log query endpoint
    - User action tracking with timestamps

Usage:
    >>> from audit import log_action, get_audit_logs
    >>> log_action("signup", "mrodriguez", {"activity": "Chess Club", "email": "student@edu"})
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pymongo import MongoClient
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

_mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017/")
_database_name = os.getenv("DATABASE_NAME", "mergington_high")
_client: Optional[MongoClient] = None


def _get_collection():
    """Get the audit_log collection (lazy connection)."""
    global _client
    if _client is None:
        _client = MongoClient(_mongodb_url, serverSelectionTimeoutMS=5000)
    return _client[_database_name]["audit_log"]


def log_action(
    action: str,
    username: str,
    details: Dict[str, Any],
    request_id: Optional[str] = None,
    ip_address: Optional[str] = None,
):
    """Record an audit log entry.

    Args:
        action: The action performed (e.g., "signup", "unregister", "cache_clear")
        username: The user who performed the action
        details: Additional details about the action
        request_id: Optional request correlation ID
        ip_address: Optional client IP address
    """
    entry = {
        "action": action,
        "username": username,
        "details": details,
        "request_id": request_id,
        "ip_address": ip_address,
        "timestamp": datetime.now(timezone.utc),
    }

    try:
        _get_collection().insert_one(entry)
        logger.info(f"Audit: {action} by {username}")
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")


def get_audit_logs(
    limit: int = 50,
    skip: int = 0,
    action_filter: Optional[str] = None,
    username_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Query audit log entries.

    Args:
        limit: Maximum entries to return
        skip: Number of entries to skip
        action_filter: Filter by action type
        username_filter: Filter by username

    Returns:
        list: Audit log entries
    """
    query = {}
    if action_filter:
        query["action"] = action_filter
    if username_filter:
        query["username"] = username_filter

    try:
        cursor = (
            _get_collection()
            .find(query)
            .sort("timestamp", -1)
            .skip(skip)
            .limit(limit)
        )
        results = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            if "timestamp" in doc and hasattr(doc["timestamp"], "isoformat"):
                doc["timestamp"] = doc["timestamp"].isoformat()
            results.append(doc)
        return results
    except Exception as e:
        logger.error(f"Failed to query audit logs: {e}")
        return []
