"""
Redis caching utilities for the High School Management System API.

This module provides:
    - Redis connection management
    - Cache key generation utilities
    - TTL-based cache operations
    - Decorator for Redis-backed caching

Usage:
    >>> from caching_redis import redis_cache, get_redis_client
    >>> client = get_redis_client()
    >>> @redis_cache(ttl=600)
    ... def expensive_operation():
    ...     return data
"""

import json
import functools
import logging
from typing import Any, Optional, Callable
import redis
from redis import Redis
import os

logger = logging.getLogger(__name__)

# Redis Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_ENABLED = os.getenv("REDIS_ENABLED", "true").lower() == "true"


class RedisCache:
    """Manager for Redis connection and cache operations."""

    _instance: Optional["RedisCache"] = None
    _client: Optional[Redis] = None
    _last_attempt: float = 0.0
    _retry_cooldown: float = 60.0

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisCache, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None and REDIS_ENABLED:
            import time
            now = time.time()
            if now - self.__class__._last_attempt < self.__class__._retry_cooldown:
                return
            self.__class__._last_attempt = now
            try:
                self._client = redis.Redis(
                    host=REDIS_HOST,
                    port=REDIS_PORT,
                    db=REDIS_DB,
                    password=REDIS_PASSWORD,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                    health_check_interval=30,
                )
                # Test connection
                self._client.ping()
                logger.info(f"Redis connected to {REDIS_HOST}:{REDIS_PORT}")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Caching disabled.")
                self._client = None

    def get_client(self) -> Optional[Redis]:
        """Get Redis client instance."""
        return self._client

    def is_connected(self) -> bool:
        """Check if Redis is connected and available."""
        if not self._client:
            return False
        try:
            self._client.ping()
            return True
        except Exception:
            return False

    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """
        Set a cache value with TTL.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds

        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            return False

        try:
            serialized_value = json.dumps(value)
            self._client.setex(key, ttl, serialized_value)
            logger.debug(f"Cache set: {key} (ttl={ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Failed to set cache {key}: {e}")
            return False

    def get(self, key: str) -> Optional[Any]:
        """
        Get a cached value.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if not self._client:
            return None

        try:
            value = self._client.get(key)
            if value is not None:
                logger.debug(f"Cache hit: {key}")
                return json.loads(value)
            logger.debug(f"Cache miss: {key}")
            return None
        except Exception as e:
            logger.error(f"Failed to get cache {key}: {e}")
            return None

    def delete(self, key: str) -> bool:
        """Delete a cache entry."""
        if not self._client:
            return False

        try:
            self._client.delete(key)
            logger.debug(f"Cache deleted: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete cache {key}: {e}")
            return False

    def clear(self, pattern: str = "*") -> int:
        """
        Clear cache entries matching pattern.

        Args:
            pattern: Key pattern to match (default: "*" for all)

        Returns:
            Number of keys deleted
        """
        if not self._client:
            return 0

        try:
            keys = list(self._client.scan_iter(match=pattern))
            if keys:
                count = self._client.delete(*keys)
                logger.debug(f"Cache cleared: {count} keys deleted")
                return count
            return 0
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return 0

    def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        if not self._client:
            return False

        try:
            return self._client.exists(key) > 0
        except Exception:
            return False

    def get_stats(self) -> dict:
        """Get Redis cache statistics."""
        if not self._client:
            return {"connected": False}

        try:
            info = self._client.info()
            return {
                "connected": True,
                "used_memory": info.get("used_memory_human", "N/A"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands": info.get("total_commands_processed", 0),
                "uptime_seconds": info.get("uptime_in_seconds", 0),
            }
        except Exception as e:
            logger.error(f"Failed to get Redis stats: {e}")
            return {"connected": False, "error": str(e)}


def get_redis_client() -> Optional[Redis]:
    """
    Get the Redis client singleton.

    Returns:
        Redis client instance or None if not connected
    """
    cache = RedisCache()
    return cache.get_client()


def redis_cache(ttl: int = 300):
    """
    Decorator for caching function results in Redis.

    Args:
        ttl: Time to live in seconds

    Example:
        >>> @redis_cache(ttl=600)
        ... def get_activities():
        ...     # Expensive operation
        ...     return activities
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache = RedisCache()

            # Create cache key from function name and arguments
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"

            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Redis cache hit for {func.__name__}")
                return cached_value

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            logger.debug(f"Redis cached result for {func.__name__}")

            return result

        return wrapper

    return decorator
