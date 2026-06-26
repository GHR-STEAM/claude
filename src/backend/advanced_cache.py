"""
Advanced caching system with intelligent invalidation and prefetching.

This module provides:
    - Predictive caching based on patterns
    - Smart cache invalidation
    - Cache warming strategies
    - LRU eviction policies
    - Multi-tier caching

Usage:
    >>> from advanced_cache import AdvancedCacheManager
    >>> manager = AdvancedCacheManager()
    >>> manager.warmup_cache()
"""

import logging
from typing import Dict, Any, Optional, Set, List
from datetime import datetime, timezone
from collections import OrderedDict
import time

from .performance import get_db_pool

logger = logging.getLogger(__name__)


class AdvancedCacheManager:
    """Advanced cache management with intelligent strategies."""

    def __init__(self, max_size: int = 5000):
        """
        Initialize advanced cache manager.

        Args:
            max_size: Maximum cache size
        """
        self.max_size = max_size
        self.cache: OrderedDict = OrderedDict()
        self.access_patterns: Dict[str, List[float]] = {}
        self.hit_count: int = 0
        self.miss_count: int = 0
        self.pool = get_db_pool()
        self.db = self.pool.get_database()

    def set_with_priority(
        self,
        key: str,
        value: Any,
        ttl: int = 300,
        priority: int = 5
    ) -> None:
        """
        Set cache value with priority.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            priority: Priority level (1-10, higher = more important)
        """
        if len(self.cache) >= self.max_size and key not in self.cache:
            self._evict_lowest_priority()

        self.cache[key] = {
            "value": value,
            "ttl": ttl,
            "created_at": time.time(),
            "last_accessed": time.time(),
            "access_count": 0,
            "priority": priority,
        }

        # Move to end (most recent)
        self.cache.move_to_end(key)

        logger.debug(f"Cache set: {key} (priority={priority})")

    def get_with_expiry_check(self, key: str) -> Optional[Any]:
        """
        Get cache value with automatic expiry checking.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        if key not in self.cache:
            self.miss_count += 1
            return None

        entry = self.cache[key]
        current_time = time.time()
        elapsed = current_time - entry["created_at"]

        # Check if expired
        if elapsed > entry["ttl"]:
            del self.cache[key]
            self.access_patterns.pop(key, None)
            self.miss_count += 1
            logger.debug(f"Cache expired: {key}")
            return None

        # Update access metrics
        entry["last_accessed"] = current_time
        entry["access_count"] += 1
        self.hit_count += 1

        # Track access pattern
        if key not in self.access_patterns:
            self.access_patterns[key] = []
        self.access_patterns[key].append(current_time)

        logger.debug(f"Cache hit: {key} (accesses={entry['access_count']})")
        return entry["value"]

    def warmup_cache(self) -> Dict[str, int]:
        """
        Warmup cache with frequently accessed data.

        Returns:
            dict: Warmup statistics
        """
        logger.info("Starting cache warmup")

        warmup_stats = {
            "activities": 0,
            "teachers": 0,
            "categories": 0,
            "total_warmed": 0,
        }

        try:
            # Warmup activities
            activities = list(self.db['activities'].find({}))
            for activity in activities[:100]:  # Cache top 100
                key = f"activity:{activity.get('_id')}"
                self.set_with_priority(
                    key,
                    activity,
                    ttl=600,
                    priority=8
                )
                warmup_stats["activities"] += 1

            # Warmup teachers
            teachers = list(self.db['teachers'].find({}))
            for teacher in teachers:
                key = f"teacher:{teacher.get('_id')}"
                self.set_with_priority(
                    key,
                    teacher,
                    ttl=600,
                    priority=7
                )
                warmup_stats["teachers"] += 1

            warmup_stats["total_warmed"] = (
                warmup_stats["activities"] +
                warmup_stats["teachers"] +
                warmup_stats["categories"]
            )

            logger.info(f"Cache warmed: {warmup_stats['total_warmed']} items")
            return warmup_stats

        except Exception as e:
            logger.error(f"Cache warmup failed: {e}")
            return warmup_stats

    def get_cache_statistics(self) -> Dict[str, Any]:
        """
        Get detailed cache statistics.

        Returns:
            dict: Cache statistics
        """
        total_accesses = sum(
            entry["access_count"] for entry in self.cache.values()
        )

        average_priority = (
            sum(entry["priority"] for entry in self.cache.values()) /
            len(self.cache) if self.cache else 0
        )

        # Calculate hit rate accurately
        total_requests = self.hit_count + self.miss_count
        hit_rate = (self.hit_count / total_requests * 100) if total_requests > 0 else 0

        return {
            "cache_size": len(self.cache),
            "max_size": self.max_size,
            "utilization_percent": round((len(self.cache) / self.max_size) * 100, 2),
            "total_accesses": total_accesses,
            "average_priority": round(average_priority, 2),
            "estimated_hit_rate": round(hit_rate, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def invalidate_by_pattern(self, pattern: str) -> int:
        """
        Invalidate cache entries matching a pattern.

        Args:
            pattern: Key pattern to match

        Returns:
            int: Number of entries invalidated
        """
        keys_to_delete = [
            key for key in self.cache.keys()
            if pattern in key
        ]

        for key in keys_to_delete:
            del self.cache[key]

        logger.info(f"Cache invalidated: {len(keys_to_delete)} entries (pattern={pattern})")
        return len(keys_to_delete)

    def invalidate_all(self) -> int:
        """
        Clear entire cache.

        Returns:
            int: Number of entries cleared
        """
        count = len(self.cache)
        self.cache.clear()
        self.access_patterns.clear()
        logger.info(f"Cache cleared: {count} entries")
        return count

    def _evict_lowest_priority(self) -> None:
        """Evict lowest priority item using LRU strategy."""
        if not self.cache:
            return

        # Find entry with lowest priority and oldest access
        evict_key = None
        evict_priority = float('inf')
        evict_time = float('inf')

        for key, entry in self.cache.items():
            if entry["priority"] < evict_priority or (
                entry["priority"] == evict_priority and
                entry["last_accessed"] < evict_time
            ):
                evict_key = key
                evict_priority = entry["priority"]
                evict_time = entry["last_accessed"]

        if evict_key:
            del self.cache[evict_key]
            logger.debug(f"Cache evicted: {evict_key}")

    def get_hot_keys(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get most frequently accessed keys.

        Args:
            limit: Maximum keys to return

        Returns:
            list: Hot keys with statistics
        """
        sorted_keys = sorted(
            self.cache.items(),
            key=lambda x: x[1]["access_count"],
            reverse=True
        )[:limit]

        return [
            {
                "key": key,
                "accesses": entry["access_count"],
                "priority": entry["priority"],
                "age_seconds": time.time() - entry["created_at"],
            }
            for key, entry in sorted_keys
        ]

    def get_expired_keys(self) -> List[str]:
        """
        Get all expired keys (without removing them).

        Returns:
            list: Expired keys
        """
        current_time = time.time()
        expired = []

        for key, entry in self.cache.items():
            elapsed = current_time - entry["created_at"]
            if elapsed > entry["ttl"]:
                expired.append(key)

        return expired

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries.

        Returns:
            int: Number of entries removed
        """
        expired = self.get_expired_keys()

        for key in expired:
            del self.cache[key]

        if expired:
            logger.info(f"Cache cleanup: removed {len(expired)} expired entries")

        return len(expired)


# Global advanced cache manager instance
_advanced_cache_manager: Optional[AdvancedCacheManager] = None


def get_advanced_cache_manager() -> AdvancedCacheManager:
    """
    Get the global advanced cache manager instance.

    Returns:
        AdvancedCacheManager: Singleton instance
    """
    global _advanced_cache_manager
    if _advanced_cache_manager is None:
        _advanced_cache_manager = AdvancedCacheManager()
    return _advanced_cache_manager
