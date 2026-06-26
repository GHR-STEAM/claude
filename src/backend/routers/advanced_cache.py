"""
Advanced cache management endpoints for the High School Management System API.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List

from ..advanced_cache import get_advanced_cache_manager

router = APIRouter(
    prefix="/cache",
    tags=["cache"]
)


@router.post("/warmup", response_model=Dict[str, Any])
def warmup_cache() -> Dict[str, Any]:
    """
    Warmup cache with frequently accessed data.

    Returns:
        dict: Warmup statistics
    """
    try:
        manager = get_advanced_cache_manager()
        stats = manager.warmup_cache()

        return {
            "message": "Cache warmed successfully",
            "statistics": stats,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache warmup failed: {str(e)}")


@router.get("/statistics", response_model=Dict[str, Any])
def get_cache_statistics() -> Dict[str, Any]:
    """
    Get detailed cache statistics.

    Returns:
        dict: Cache statistics
    """
    try:
        manager = get_advanced_cache_manager()
        return manager.get_cache_statistics()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


@router.get("/hot-keys", response_model=Dict[str, Any])
def get_hot_keys(
    limit: int = Query(20, ge=1, le=100, description="Maximum keys to return")
) -> Dict[str, Any]:
    """
    Get most frequently accessed cache keys.

    Query Parameters:
    - limit: Maximum keys to return (1-100, default 20)

    Returns:
        dict: Hot keys with statistics
    """
    try:
        manager = get_advanced_cache_manager()
        keys = manager.get_hot_keys(limit=limit)

        return {
            "total": len(keys),
            "hot_keys": keys,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get hot keys: {str(e)}")


@router.get("/expired-keys", response_model=Dict[str, Any])
def get_expired_keys() -> Dict[str, Any]:
    """
    Get all expired cache keys.

    Returns:
        dict: Expired keys list
    """
    try:
        manager = get_advanced_cache_manager()
        expired = manager.get_expired_keys()

        return {
            "total": len(expired),
            "expired_keys": expired,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get expired keys: {str(e)}")


@router.post("/cleanup", response_model=Dict[str, Any])
def cleanup_expired() -> Dict[str, Any]:
    """
    Remove all expired cache entries.

    Returns:
        dict: Cleanup statistics
    """
    try:
        manager = get_advanced_cache_manager()
        count = manager.cleanup_expired()

        return {
            "message": "Cache cleanup completed",
            "entries_removed": count,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@router.post("/invalidate", response_model=Dict[str, Any])
def invalidate_by_pattern(
    pattern: str = Query(..., description="Key pattern to match")
) -> Dict[str, Any]:
    """
    Invalidate cache entries matching a pattern.

    Query Parameters:
    - pattern: Key pattern to match

    Returns:
        dict: Number of entries invalidated
    """
    try:
        manager = get_advanced_cache_manager()
        count = manager.invalidate_by_pattern(pattern)

        return {
            "message": "Cache invalidated",
            "entries_removed": count,
            "pattern": pattern,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Invalidation failed: {str(e)}")


@router.post("/clear", response_model=Dict[str, Any])
def clear_all_cache() -> Dict[str, Any]:
    """
    Clear entire cache.

    Returns:
        dict: Clear status and count
    """
    try:
        manager = get_advanced_cache_manager()
        count = manager.invalidate_all()

        return {
            "message": "Cache cleared successfully",
            "entries_cleared": count,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Clear failed: {str(e)}")
