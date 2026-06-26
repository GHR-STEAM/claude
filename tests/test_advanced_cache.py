"""
Comprehensive tests for advanced caching system.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from src.backend.advanced_cache import AdvancedCacheManager


@pytest.fixture
def mock_db():
    """Mock MongoDB database."""
    db = MagicMock()
    db.__getitem__ = MagicMock()
    return db


@pytest.fixture
def cache_manager(mock_db):
    """Create AdvancedCacheManager with mocked database."""
    with patch('src.backend.advanced_cache.get_db_pool') as mock_pool:
        mock_pool_instance = MagicMock()
        mock_pool_instance.get_database.return_value = mock_db
        mock_pool.return_value = mock_pool_instance

        manager = AdvancedCacheManager(max_size=5000)
        manager.db = mock_db
        return manager


class TestCacheBasics:
    """Tests for basic cache operations."""

    def test_set_cache_value(self, cache_manager):
        """Test setting a cache value."""
        cache_manager.set_with_priority("key1", "value1", ttl=300, priority=5)

        assert "key1" in cache_manager.cache
        assert cache_manager.cache["key1"]["value"] == "value1"
        assert cache_manager.cache["key1"]["ttl"] == 300

    def test_get_cache_value(self, cache_manager):
        """Test retrieving a cache value."""
        cache_manager.set_with_priority("key1", "value1")
        result = cache_manager.get_with_expiry_check("key1")

        assert result == "value1"

    def test_get_nonexistent_value(self, cache_manager):
        """Test retrieving non-existent value returns None."""
        result = cache_manager.get_with_expiry_check("nonexistent")

        assert result is None

    def test_cache_expiry(self, cache_manager):
        """Test cache value expires after TTL."""
        cache_manager.set_with_priority("key1", "value1", ttl=1)
        time.sleep(1.1)

        result = cache_manager.get_with_expiry_check("key1")

        assert result is None
        assert "key1" not in cache_manager.cache

    def test_cache_not_expired(self, cache_manager):
        """Test cache value before expiry."""
        cache_manager.set_with_priority("key1", "value1", ttl=10)
        time.sleep(0.1)

        result = cache_manager.get_with_expiry_check("key1")

        assert result == "value1"


class TestPriorityAndEviction:
    """Tests for priority-based eviction."""

    def test_priority_levels(self, cache_manager):
        """Test priority levels are stored correctly."""
        cache_manager.set_with_priority("key1", "value1", priority=1)
        cache_manager.set_with_priority("key2", "value2", priority=10)

        assert cache_manager.cache["key1"]["priority"] == 1
        assert cache_manager.cache["key2"]["priority"] == 10

    def test_evict_lowest_priority(self, cache_manager):
        """Test that lowest priority item is evicted first."""
        # Fill cache beyond max_size to trigger eviction
        cache_manager.max_size = 3
        cache_manager.set_with_priority("low", "value1", priority=1)
        cache_manager.set_with_priority("med", "value2", priority=5)
        cache_manager.set_with_priority("high", "value3", priority=10)

        # Add one more to trigger eviction
        cache_manager.set_with_priority("new", "value4", priority=5)

        # Low priority should be evicted
        assert "low" not in cache_manager.cache
        assert "med" in cache_manager.cache
        assert "high" in cache_manager.cache
        assert "new" in cache_manager.cache

    def test_evict_lru_within_same_priority(self, cache_manager):
        """Test LRU eviction within same priority level."""
        cache_manager.max_size = 3
        cache_manager.set_with_priority("key1", "value1", priority=5)
        cache_manager.set_with_priority("key2", "value2", priority=5)
        cache_manager.set_with_priority("key3", "value3", priority=5)

        # Access key2 to make it more recently used
        cache_manager.get_with_expiry_check("key2")

        # Add new item to trigger eviction
        cache_manager.set_with_priority("key4", "value4", priority=5)

        # key1 should be evicted (oldest with same priority)
        assert "key1" not in cache_manager.cache
        assert "key2" in cache_manager.cache
        assert "key3" in cache_manager.cache

    def test_eviction_respects_max_size(self, cache_manager):
        """Test cache respects max_size limit."""
        cache_manager.max_size = 100
        for i in range(100):
            cache_manager.set_with_priority(f"key{i}", f"value{i}")

        assert len(cache_manager.cache) == 100

        # Add one more - should trigger eviction
        cache_manager.set_with_priority("key100", "value100")

        assert len(cache_manager.cache) == 100


class TestAccessTracking:
    """Tests for access pattern tracking."""

    def test_access_count_incremented(self, cache_manager):
        """Test access count is incremented on cache hit."""
        cache_manager.set_with_priority("key1", "value1")
        assert cache_manager.cache["key1"]["access_count"] == 0

        cache_manager.get_with_expiry_check("key1")
        assert cache_manager.cache["key1"]["access_count"] == 1

        cache_manager.get_with_expiry_check("key1")
        assert cache_manager.cache["key1"]["access_count"] == 2

    def test_access_pattern_tracking(self, cache_manager):
        """Test access patterns are tracked."""
        cache_manager.set_with_priority("key1", "value1")
        cache_manager.get_with_expiry_check("key1")
        cache_manager.get_with_expiry_check("key1")

        assert "key1" in cache_manager.access_patterns
        assert len(cache_manager.access_patterns["key1"]) == 2

    def test_last_accessed_updated(self, cache_manager):
        """Test last_accessed timestamp is updated."""
        cache_manager.set_with_priority("key1", "value1")
        initial_access = cache_manager.cache["key1"]["last_accessed"]

        time.sleep(0.1)
        cache_manager.get_with_expiry_check("key1")
        new_access = cache_manager.cache["key1"]["last_accessed"]

        assert new_access > initial_access


class TestCacheWarming:
    """Tests for cache warmup functionality."""

    def test_warmup_cache_creates_entries(self, cache_manager, mock_db):
        """Test warmup_cache populates cache."""
        mock_activities = [{"_id": f"activity{i}"} for i in range(50)]
        mock_teachers = [{"_id": f"teacher{i}"} for i in range(10)]

        mock_activities_collection = MagicMock()
        mock_activities_collection.find.return_value = mock_activities
        mock_teachers_collection = MagicMock()
        mock_teachers_collection.find.return_value = mock_teachers

        def getitem_side_effect(key):
            if key == "activities":
                return mock_activities_collection
            elif key == "teachers":
                return mock_teachers_collection

        mock_db.__getitem__.side_effect = getitem_side_effect

        stats = cache_manager.warmup_cache()

        assert stats["activities"] > 0
        assert stats["teachers"] > 0
        assert stats["total_warmed"] > 0

    def test_warmup_stats_returns_counts(self, cache_manager, mock_db):
        """Test warmup returns statistics."""
        mock_db.__getitem__.return_value = MagicMock(find=MagicMock(return_value=[]))

        stats = cache_manager.warmup_cache()

        assert "activities" in stats
        assert "teachers" in stats
        assert "categories" in stats
        assert "total_warmed" in stats


class TestCacheStatistics:
    """Tests for cache statistics."""

    def test_cache_statistics(self, cache_manager):
        """Test cache statistics calculation."""
        cache_manager.set_with_priority("key1", "value1", priority=5)
        cache_manager.set_with_priority("key2", "value2", priority=8)
        cache_manager.get_with_expiry_check("key1")
        cache_manager.get_with_expiry_check("key1")

        stats = cache_manager.get_cache_statistics()

        assert stats["cache_size"] == 2
        assert stats["max_size"] == 5000
        assert stats["utilization_percent"] == 0.04
        assert stats["total_accesses"] == 2

    def test_average_priority(self, cache_manager):
        """Test average priority calculation."""
        cache_manager.set_with_priority("key1", "value1", priority=2)
        cache_manager.set_with_priority("key2", "value2", priority=8)

        stats = cache_manager.get_cache_statistics()

        assert stats["average_priority"] == 5.0

    def test_hit_rate_calculation(self, cache_manager):
        """Test hit rate calculation."""
        cache_manager.set_with_priority("key1", "value1")
        cache_manager.get_with_expiry_check("key1")
        cache_manager.get_with_expiry_check("key1")
        cache_manager.get_with_expiry_check("nonexistent")

        stats = cache_manager.get_cache_statistics()

        # Hit rate should reflect successful accesses
        assert "estimated_hit_rate" in stats

    def test_statistics_timestamp(self, cache_manager):
        """Test statistics include timestamp."""
        stats = cache_manager.get_cache_statistics()

        assert "timestamp" in stats
        # Verify timestamp is ISO format
        from datetime import datetime
        datetime.fromisoformat(stats["timestamp"].replace("Z", "+00:00"))


class TestInvalidation:
    """Tests for cache invalidation."""

    def test_invalidate_by_pattern(self, cache_manager):
        """Test pattern-based invalidation."""
        cache_manager.set_with_priority("activity:1", "value1")
        cache_manager.set_with_priority("activity:2", "value2")
        cache_manager.set_with_priority("teacher:1", "value3")

        count = cache_manager.invalidate_by_pattern("activity")

        assert count == 2
        assert "activity:1" not in cache_manager.cache
        assert "activity:2" not in cache_manager.cache
        assert "teacher:1" in cache_manager.cache

    def test_invalidate_all(self, cache_manager):
        """Test clearing entire cache."""
        cache_manager.set_with_priority("key1", "value1")
        cache_manager.set_with_priority("key2", "value2")
        cache_manager.get_with_expiry_check("key1")  # Add access pattern

        count = cache_manager.invalidate_all()

        assert count == 2
        assert len(cache_manager.cache) == 0
        assert len(cache_manager.access_patterns) == 0

    def test_invalidate_empty_cache(self, cache_manager):
        """Test invalidation on empty cache."""
        count = cache_manager.invalidate_by_pattern("activity")

        assert count == 0


class TestExpiredKeys:
    """Tests for expired key management."""

    def test_get_expired_keys(self, cache_manager):
        """Test identifying expired keys."""
        cache_manager.set_with_priority("valid", "value", ttl=10)
        cache_manager.set_with_priority("expired", "value", ttl=1)
        time.sleep(1.1)

        expired = cache_manager.get_expired_keys()

        assert "expired" in expired
        assert "valid" not in expired

    def test_cleanup_expired(self, cache_manager):
        """Test cleanup removes expired entries."""
        cache_manager.set_with_priority("valid", "value", ttl=10)
        cache_manager.set_with_priority("expired", "value", ttl=1)
        time.sleep(1.1)

        count = cache_manager.cleanup_expired()

        assert count == 1
        assert "valid" in cache_manager.cache
        assert "expired" not in cache_manager.cache

    def test_cleanup_no_expired(self, cache_manager):
        """Test cleanup with no expired entries."""
        cache_manager.set_with_priority("key1", "value")

        count = cache_manager.cleanup_expired()

        assert count == 0


class TestHotKeys:
    """Tests for hot key identification."""

    def test_get_hot_keys(self, cache_manager):
        """Test identifying most accessed keys."""
        cache_manager.set_with_priority("key1", "value1")
        cache_manager.set_with_priority("key2", "value2")

        # Access key1 multiple times
        for _ in range(5):
            cache_manager.get_with_expiry_check("key1")

        # Access key2 once
        cache_manager.get_with_expiry_check("key2")

        hot_keys = cache_manager.get_hot_keys(limit=10)

        assert len(hot_keys) == 2
        assert hot_keys[0]["key"] == "key1"
        assert hot_keys[0]["accesses"] == 5
        assert hot_keys[1]["key"] == "key2"
        assert hot_keys[1]["accesses"] == 1

    def test_hot_keys_limit(self, cache_manager):
        """Test hot keys respects limit parameter."""
        for i in range(50):
            cache_manager.set_with_priority(f"key{i}", f"value{i}")

        hot_keys = cache_manager.get_hot_keys(limit=10)

        assert len(hot_keys) <= 10

    def test_hot_keys_includes_stats(self, cache_manager):
        """Test hot keys include all statistics."""
        cache_manager.set_with_priority("key1", "value1", priority=7)
        cache_manager.get_with_expiry_check("key1")

        hot_keys = cache_manager.get_hot_keys(limit=10)

        assert len(hot_keys) == 1
        key = hot_keys[0]
        assert "key" in key
        assert "accesses" in key
        assert "priority" in key
        assert "age_seconds" in key


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_cache_statistics(self, cache_manager):
        """Test statistics on empty cache."""
        stats = cache_manager.get_cache_statistics()

        assert stats["cache_size"] == 0
        assert stats["total_accesses"] == 0
        assert stats["average_priority"] == 0

    def test_priority_boundaries(self, cache_manager):
        """Test priority boundary values."""
        cache_manager.set_with_priority("min", "value", priority=1)
        cache_manager.set_with_priority("max", "value", priority=10)

        assert cache_manager.cache["min"]["priority"] == 1
        assert cache_manager.cache["max"]["priority"] == 10

    def test_ttl_zero(self, cache_manager):
        """Test TTL of zero."""
        cache_manager.set_with_priority("key", "value", ttl=0)
        time.sleep(0.1)

        result = cache_manager.get_with_expiry_check("key")

        assert result is None

    def test_large_values(self, cache_manager):
        """Test caching large values."""
        large_value = "x" * 10000
        cache_manager.set_with_priority("large", large_value)

        result = cache_manager.get_with_expiry_check("large")

        assert result == large_value

    def test_special_characters_in_keys(self, cache_manager):
        """Test keys with special characters."""
        special_key = "key:with:colons:and-dashes_and_underscores"
        cache_manager.set_with_priority(special_key, "value")

        result = cache_manager.get_with_expiry_check(special_key)

        assert result == "value"

    def test_none_values(self, cache_manager):
        """Test caching None values."""
        cache_manager.set_with_priority("none_key", None)

        result = cache_manager.get_with_expiry_check("none_key")

        assert result is None
        # But key should still be in cache
        assert "none_key" in cache_manager.cache

    def test_eviction_preserves_high_priority(self, cache_manager):
        """Test that high priority items are preserved during eviction."""
        cache_manager.max_size = 3
        cache_manager.set_with_priority("critical", "value", priority=10)
        cache_manager.set_with_priority("low1", "value", priority=1)
        cache_manager.set_with_priority("low2", "value", priority=1)

        # Trigger eviction
        cache_manager.set_with_priority("new", "value", priority=5)

        # Critical should still be there
        assert "critical" in cache_manager.cache
        assert len(cache_manager.cache) == 3


class TestCacheConcurrency:
    """Tests for cache behavior under concurrent-like scenarios."""

    def test_multiple_sequential_operations(self, cache_manager):
        """Test multiple operations in sequence."""
        for i in range(100):
            cache_manager.set_with_priority(f"key{i}", f"value{i}")
            result = cache_manager.get_with_expiry_check(f"key{i}")
            assert result == f"value{i}"

    def test_mix_of_operations(self, cache_manager):
        """Test mix of different operations."""
        cache_manager.set_with_priority("key1", "value1", priority=5)
        cache_manager.set_with_priority("key2", "value2", priority=8)
        cache_manager.get_with_expiry_check("key1")
        cache_manager.invalidate_by_pattern("key")
        cache_manager.set_with_priority("key3", "value3")

        stats = cache_manager.get_cache_statistics()

        assert stats["cache_size"] == 1
        assert "key1" not in cache_manager.cache
        assert "key2" not in cache_manager.cache
        assert "key3" in cache_manager.cache
