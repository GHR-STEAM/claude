"""
Performance optimization utilities for the High School Management System API.

This module provides:
    - Connection pooling for MongoDB
    - Query optimization helpers
    - Response caching utilities
    - Performance monitoring

Usage:
    >>> from performance import get_db_pool
    >>> pool = get_db_pool()
    >>> collection = pool.database['activities']
"""

import functools
import time
from typing import Any, Callable, Optional, Dict
import pymongo
from pymongo import MongoClient
import logging

logger = logging.getLogger(__name__)

# MongoDB Connection Pool Configuration
POOL_CONFIG = {
    "maxPoolSize": 50,
    "minPoolSize": 10,
    "maxIdleTimeMS": 45000,
    "waitQueueTimeoutMS": 10000,
    "serverSelectionTimeoutMS": 5000,
}


class DatabasePool:
    """Singleton for MongoDB connection pool."""

    _instance: Optional["DatabasePool"] = None
    _client: Optional[MongoClient] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabasePool, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None:
            import os
            from dotenv import load_dotenv

            load_dotenv()

            mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017/")
            database_name = os.getenv("DATABASE_NAME", "mergington_high")

            self._client = MongoClient(
                mongodb_url,
                **POOL_CONFIG
            )
            self.db = self._client[database_name]
            logger.info("Database pool initialized with connection pooling")

    def get_client(self) -> MongoClient:
        """Get the MongoDB client."""
        return self._client

    def get_database(self):
        """Get the database instance."""
        return self.db

    def close(self):
        """Close the connection pool."""
        if self._client:
            self._client.close()
            logger.info("Database pool closed")


def get_db_pool() -> DatabasePool:
    """
    Get the database pool singleton.

    Returns:
        DatabasePool: Singleton instance with connection pooling

    Example:
        >>> pool = get_db_pool()
        >>> db = pool.get_database()
    """
    return DatabasePool()


class PerformanceCache:
    """Simple in-memory cache for performance optimization."""

    _cache: Dict[str, tuple] = {}
    _max_size: int = 1000

    @classmethod
    def set(cls, key: str, value: Any, ttl: int = 300):
        """
        Set a cache value with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default: 300)
        """
        now = time.time()
        if len(cls._cache) >= cls._max_size:
            expired_keys = [k for k, (_, exp) in cls._cache.items() if now > exp]
            for k in expired_keys:
                del cls._cache[k]
            if len(cls._cache) >= cls._max_size:
                first_key = next(iter(cls._cache))
                del cls._cache[first_key]
        cls._cache[key] = (value, time.time() + ttl)

    @classmethod
    def get(cls, key: str) -> Optional[Any]:
        """
        Get a cached value if not expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if expired/not found
        """
        if key not in cls._cache:
            return None

        value, expiry = cls._cache[key]
        if time.time() > expiry:
            del cls._cache[key]
            return None

        return value

    @classmethod
    def delete(cls, key: str):
        """Delete a cache entry."""
        if key in cls._cache:
            del cls._cache[key]

    @classmethod
    def clear(cls):
        """Clear all cache entries."""
        cls._cache.clear()


def cache(ttl: int = 300):
    """
    Decorator for caching function results.

    Args:
        ttl: Time to live in seconds

    Example:
        >>> @cache(ttl=600)
        ... def get_activities():
        ...     # Expensive operation
        ...     return activities
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"

            # Try to get from cache
            cached_value = PerformanceCache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_value

            # Execute function and cache result
            result = func(*args, **kwargs)
            PerformanceCache.set(cache_key, result, ttl)
            logger.debug(f"Cached result for {func.__name__}")

            return result

        return wrapper

    return decorator


def measure_performance(func: Callable) -> Callable:
    """
    Decorator to measure function execution time.

    Logs the execution time for performance monitoring.

    Example:
        >>> @measure_performance
        ... def expensive_operation():
        ...     pass
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed_time = time.time() - start_time

        logger.info(
            f"{func.__name__} executed in {elapsed_time:.3f} seconds"
        )

        return result

    return wrapper


class QueryOptimizer:
    """Utilities for optimizing MongoDB queries."""

    @staticmethod
    def create_index(collection, field: str, unique: bool = False):
        """
        Create an index on a collection field.

        Args:
            collection: MongoDB collection
            field: Field name to index
            unique: Whether the index should be unique
        """
        try:
            collection.create_index(field, unique=unique)
            logger.info(f"Index created on {field}")
        except Exception as e:
            logger.error(f"Failed to create index: {e}")

    @staticmethod
    def create_text_index(collection, field: str):
        """
        Create a text search index.

        Args:
            collection: MongoDB collection
            field: Field to create text index on
        """
        try:
            collection.create_index([(field, "text")])
            logger.info(f"Text index created on {field}")
        except Exception as e:
            logger.error(f"Failed to create text index: {e}")


# Initialize performance cache on startup
def init_performance():
    """Initialize performance optimizations."""
    try:
        pool = get_db_pool()
        logger.info("Performance optimizations initialized")
    except Exception as e:
        logger.error(f"Failed to initialize performance: {e}")
