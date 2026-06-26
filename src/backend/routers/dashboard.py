"""
Dashboard endpoints for the High School Management System API.

This module provides:
    - Health check endpoint
    - Application statistics
    - Performance metrics
    - Cache status information
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from datetime import datetime, timezone
import logging

from ..performance import get_db_pool, PerformanceCache
from ..caching_redis import RedisCache
from ..metrics import metrics_collector
from ..query_optimization import get_index_status
from ..backup import get_backup_manager

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"]
)


@router.get("/health", response_model=Dict[str, Any])
def health_check() -> Dict[str, Any]:
    """
    Check application health status.

    Returns:
        dict: Health status including database and cache connectivity
    """
    try:
        pool = get_db_pool()
        db_client = pool.get_client()

        # Check MongoDB connection
        db_status = "healthy"
        try:
            db_client.admin.command('ismaster')
        except Exception as e:
            db_status = "unhealthy"
            logger.error(f"Database health check failed: {e}")

        # Check Redis connection
        redis_cache = RedisCache()
        redis_status = "healthy" if redis_cache.is_connected() else "unhealthy"

        return {
            "status": "healthy" if db_status == "healthy" else "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": db_status,
            "redis": redis_status,
            "version": "1.0.0",
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail="Health check failed")


@router.get("/stats", response_model=Dict[str, Any])
def get_statistics() -> Dict[str, Any]:
    """
    Get application statistics including activity and user counts.

    Returns:
        dict: Statistics about activities, students, and teachers
    """
    try:
        pool = get_db_pool()
        db = pool.get_database()

        activities_collection = db['activities']
        teachers_collection = db['teachers']

        # Count collections
        activity_count = activities_collection.count_documents({})
        teacher_count = teachers_collection.count_documents({})

        # Count total participants across all activities using aggregation
        pipeline = [
            {"$project": {"num_participants": {"$size": {"$ifNull": ["$participants", []]}}}},
            {"$group": {"_id": None, "total": {"$sum": "$num_participants"}}}
        ]
        aggregation_result = list(activities_collection.aggregate(pipeline))
        total_participants = aggregation_result[0]["total"] if aggregation_result else 0

        # Calculate average participants per activity
        avg_participants = (
            total_participants / activity_count if activity_count > 0 else 0
        )

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "activities": {
                "total": activity_count,
                "total_participants": total_participants,
                "avg_participants": round(avg_participants, 2),
            },
            "teachers": {
                "total": teacher_count,
            },
            "cache": {
                "entries": len(PerformanceCache._cache),
            },
        }
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


@router.get("/metrics", response_model=Dict[str, Any])
def get_metrics() -> Dict[str, Any]:
    """
    Get performance metrics for the application.

    Returns:
        dict: Performance metrics including cache and database information
    """
    try:
        redis_cache = RedisCache()
        redis_stats = redis_cache.get_stats()

        pool = get_db_pool()
        db = pool.get_database()

        # Get MongoDB stats
        try:
            stats = db.command("dbStats")
            db_metrics = {
                "collections": stats.get("collections", 0),
                "data_size_mb": round(stats.get("dataSize", 0) / (1024 * 1024), 2),
                "storage_size_mb": round(stats.get("storageSize", 0) / (1024 * 1024), 2),
                "indexes": stats.get("indexes", 0),
            }
        except Exception as e:
            logger.warning(f"Failed to get MongoDB stats: {e}")
            db_metrics = {"error": "Unable to retrieve MongoDB metrics"}

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cache": {
                "type": "in-memory",
                "entries": len(PerformanceCache._cache),
            },
            "redis": redis_stats,
            "database": db_metrics,
        }
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")


@router.get("/cache-status", response_model=Dict[str, Any])
def get_cache_status() -> Dict[str, Any]:
    """
    Get detailed cache status information.

    Returns:
        dict: Cache status for both in-memory and Redis caches
    """
    try:
        # In-memory cache stats
        in_memory_cache = PerformanceCache._cache
        in_memory_stats = {
            "entries": len(in_memory_cache),
            "keys": list(in_memory_cache.keys())[:10],  # First 10 keys
        }

        # Redis cache stats
        redis_cache = RedisCache()
        redis_connected = redis_cache.is_connected()

        if redis_connected:
            try:
                client = redis_cache.get_client()
                redis_keys = client.dbsize()
                redis_stats = {
                    "connected": True,
                    "entries": redis_keys,
                    **redis_cache.get_stats(),
                }
            except Exception as e:
                logger.warning(f"Failed to get Redis details: {e}")
                redis_stats = {
                    "connected": False,
                    "error": str(e),
                }
        else:
            redis_stats = {
                "connected": False,
                "entries": 0,
            }

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "in_memory": in_memory_stats,
            "redis": redis_stats,
        }
    except Exception as e:
        logger.error(f"Failed to get cache status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cache status")


@router.post("/cache/clear", response_model=Dict[str, str])
def clear_cache() -> Dict[str, str]:
    """
    Clear all cache entries (both in-memory and Redis).

    Returns:
        dict: Confirmation message
    """
    try:
        # Clear in-memory cache
        PerformanceCache.clear()

        # Clear Redis cache
        redis_cache = RedisCache()
        redis_cache.clear()

        logger.info("All caches cleared")
        return {"message": "Cache cleared successfully"}
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")


@router.get("/metrics-advanced", response_model=Dict[str, Any])
def get_advanced_metrics() -> Dict[str, Any]:
    """
    Get advanced request metrics including latency percentiles and status codes.

    Returns:
        dict: Advanced metrics snapshot with p50/p95/p99 latency, request counts, and top endpoints
    """
    return metrics_collector.get_snapshot()


@router.post("/metrics/reset", response_model=Dict[str, str])
def reset_metrics() -> Dict[str, str]:
    """
    Reset all collected metrics.

    Returns:
        dict: Confirmation message
    """
    metrics_collector.reset()
    return {"message": "Metrics reset successfully"}


@router.get("/indexes", response_model=Dict[str, Any])
def get_indexes() -> Dict[str, Any]:
    """
    Get database index status for all collections.

    Returns:
        dict: Index information per collection
    """
    try:
        pool = get_db_pool()
        db = pool.get_database()
        return get_index_status(db)
    except Exception as e:
        logger.error(f"Failed to get index status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve index status")


@router.get("/backups", response_model=Dict[str, Any])
def get_backups() -> Dict[str, Any]:
    """
    List available database backups.

    Returns:
        dict: List of backup files with metadata
    """
    try:
        manager = get_backup_manager()
        backups = manager.list_backups(limit=50)
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "backups": backups,
            "total": len(backups),
        }
    except Exception as e:
        logger.error(f"Failed to list backups: {e}")
        raise HTTPException(status_code=500, detail="Failed to list backups")


@router.get("/backups/verify", response_model=Dict[str, Any])
def verify_backup_endpoint(backup_id: str) -> Dict[str, Any]:
    """
    Verify a backup's integrity.

    Args:
        backup_id: Backup ID to verify

    Returns:
        dict: Verification result
    """
    try:
        manager = get_backup_manager()
        result = manager.verify_backup_integrity(backup_id)
        return {
            "backup_id": backup_id,
            "valid": result.get("is_valid", False),
            "integrity_verified": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except ValueError as e:
        error_msg = str(e)
        if "Invalid backup ID format" in error_msg:
            logger.error(f"Failed to verify backup: {e}")
            raise HTTPException(status_code=400, detail=error_msg)
        else:
            logger.error(f"Failed to verify backup: {e}")
            raise HTTPException(status_code=404, detail=error_msg)
    except Exception as e:
        logger.error(f"Failed to verify backup: {e}")
        raise HTTPException(status_code=500, detail="Failed to verify backup")
