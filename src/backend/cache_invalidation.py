"""
Automated cache invalidation for the High School Management System API.

This module provides:
    - Automatic cache invalidation on data mutations
    - Pattern-based cache key clearing
    - Integration with both in-memory and Redis caches
    - Event-driven invalidation for related cache entries

Usage:
    >>> from cache_invalidation import invalidate_activities_cache, invalidate_after_mutation
    >>> @invalidate_after_mutation("activities")
    ... def signup_for_activity(...):
    ...     pass
"""

import logging
from typing import Callable, Optional
from functools import wraps

from .performance import PerformanceCache
from .caching_redis import RedisCache

logger = logging.getLogger(__name__)


CACHE_KEY_PATTERNS = {
    "activities": [
        "get_activities",
        "paginate_query",
        "get_statistics",
        "get_metrics",
    ],
    "teachers": [
        "get_teachers",
        "check_session",
        "login",
    ],
    "dashboard": [
        "get_statistics",
        "get_metrics",
        "get_cache_status",
        "health_check",
    ],
}


def invalidate_in_memory_cache(keys: Optional[list] = None):
    """Invalidate in-memory cache entries.

    Args:
        keys: Specific cache keys to invalidate. If None, clears all.
    """
    if keys:
        for key in keys:
            PerformanceCache.delete(key)
        logger.debug(f"Invalidated {len(keys)} in-memory cache keys")
    else:
        PerformanceCache.clear()
        logger.debug("Cleared all in-memory cache")


def invalidate_redis_cache(pattern: str = "*"):
    """Invalidate Redis cache entries matching a pattern.

    Args:
        pattern: Redis key pattern to match (default: "*" for all)
    """
    cache = RedisCache()
    if cache.is_connected():
        count = cache.clear(pattern)
        logger.debug(f"Invalidated {count} Redis cache keys matching '{pattern}'")
    else:
        logger.debug("Redis not connected, skipping Redis invalidation")


def invalidate_for_domain(domain: str):
    """Invalidate all cache entries related to a domain.

    Args:
        domain: Domain name (e.g., "activities", "teachers", "dashboard")
    """
    patterns = CACHE_KEY_PATTERNS.get(domain, [])

    for pattern in patterns:
        invalidate_in_memory_cache(keys=[pattern])
        invalidate_redis_cache(pattern=f"*{pattern}*")

    invalidate_in_memory_cache(keys=patterns)
    invalidate_redis_cache(pattern=f"*{domain}*")

    logger.info(f"Cache invalidated for domain: {domain}")


def invalidate_after_mutation(domain: str) -> Callable:
    """Decorator to invalidate cache after a mutation operation.

    Args:
        domain: The domain to invalidate (e.g., "activities")

    Example:
        >>> @invalidate_after_mutation("activities")
        ... def signup_for_activity(...):
        ...     # After this succeeds, activity cache is invalidated
        ...     pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            try:
                invalidate_for_domain(domain)
            except Exception as e:
                logger.error(f"Cache invalidation failed for {domain}: {e}")
            return result

        return wrapper

    return decorator


def invalidate_activities_cache():
    """Convenience function to invalidate all activity-related cache."""
    invalidate_for_domain("activities")


def invalidate_teachers_cache():
    """Convenience function to invalidate all teacher-related cache."""
    invalidate_for_domain("teachers")


def invalidate_dashboard_cache():
    """Convenience function to invalidate all dashboard-related cache."""
    invalidate_for_domain("dashboard")


def invalidate_all():
    """Invalidate the entire cache (both in-memory and Redis)."""
    invalidate_in_memory_cache()
    invalidate_redis_cache()
    logger.info("All caches invalidated")
