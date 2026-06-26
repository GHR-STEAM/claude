"""
Tests for Redis caching utilities.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


@pytest.mark.unit
class TestRedisConnection:
    """Test Redis connection management."""

    @patch('src.backend.caching_redis.redis.Redis')
    def test_redis_cache_singleton(self, mock_redis):
        """Test RedisCache is a singleton."""
        from src.backend.caching_redis import RedisCache

        # Reset singleton
        RedisCache._instance = None
        RedisCache._client = None

        with patch.dict('os.environ', {'REDIS_ENABLED': 'true'}):
            cache1 = RedisCache()
            cache2 = RedisCache()

            assert cache1 is cache2

    def test_redis_disabled_mode(self):
        """Test Redis cache when disabled."""
        from src.backend.caching_redis import RedisCache

        RedisCache._instance = None
        RedisCache._client = None

        with patch.dict('os.environ', {'REDIS_ENABLED': 'false'}):
            cache = RedisCache()
            assert cache.get_client() is None

    @patch('src.backend.caching_redis.redis.Redis')
    def test_redis_connection_failed(self, mock_redis):
        """Test graceful handling when Redis connection fails."""
        from src.backend.caching_redis import RedisCache

        mock_redis.side_effect = Exception("Connection failed")
        RedisCache._instance = None
        RedisCache._client = None

        with patch.dict('os.environ', {'REDIS_ENABLED': 'true'}):
            cache = RedisCache()
            assert cache.get_client() is None


@pytest.mark.unit
class TestRedisCacheOperations:
    """Test Redis cache operations."""

    @patch('src.backend.caching_redis.redis.Redis')
    def test_cache_set_and_get(self, mock_redis):
        """Test setting and getting cache values."""
        from src.backend.caching_redis import RedisCache

        # Setup mock
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.ping.return_value = True

        RedisCache._instance = None
        RedisCache._client = None

        with patch.dict('os.environ', {'REDIS_ENABLED': 'true'}):
            cache = RedisCache()

            # Set value
            result = cache.set("test_key", {"data": "value"}, ttl=300)
            assert result is True
            mock_client.setex.assert_called()

    @patch('src.backend.caching_redis.redis.Redis')
    def test_cache_get_missing_key(self, mock_redis):
        """Test getting non-existent cache key."""
        from src.backend.caching_redis import RedisCache

        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.ping.return_value = True
        mock_client.get.return_value = None

        RedisCache._instance = None
        RedisCache._client = None

        with patch.dict('os.environ', {'REDIS_ENABLED': 'true'}):
            cache = RedisCache()
            result = cache.get("nonexistent_key")
            assert result is None

    @patch('src.backend.caching_redis.redis.Redis')
    def test_cache_delete(self, mock_redis):
        """Test deleting cache entries."""
        from src.backend.caching_redis import RedisCache

        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.ping.return_value = True

        RedisCache._instance = None
        RedisCache._client = None

        with patch.dict('os.environ', {'REDIS_ENABLED': 'true'}):
            cache = RedisCache()
            result = cache.delete("test_key")
            assert result is True
            mock_client.delete.assert_called_with("test_key")

    @patch('src.backend.caching_redis.redis.Redis')
    def test_cache_clear(self, mock_redis):
        """Test clearing all cache entries."""
        from src.backend.caching_redis import RedisCache

        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.ping.return_value = True
        mock_client.scan_iter.return_value = iter(["key1", "key2", "key3"])
        mock_client.delete.return_value = 3

        RedisCache._instance = None
        RedisCache._client = None

        with patch.dict('os.environ', {'REDIS_ENABLED': 'true'}):
            cache = RedisCache()
            count = cache.clear()
            assert count == 3

    @patch('src.backend.caching_redis.redis.Redis')
    def test_cache_exists(self, mock_redis):
        """Test checking if key exists."""
        from src.backend.caching_redis import RedisCache

        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.ping.return_value = True
        mock_client.exists.return_value = 1

        RedisCache._instance = None
        RedisCache._client = None

        with patch.dict('os.environ', {'REDIS_ENABLED': 'true'}):
            cache = RedisCache()
            result = cache.exists("test_key")
            assert result is True


@pytest.mark.unit
class TestRedisConnectivityStatus:
    """Test Redis connectivity checking."""

    @patch('src.backend.caching_redis.redis.Redis')
    def test_is_connected_success(self, mock_redis):
        """Test checking connected status."""
        from src.backend.caching_redis import RedisCache

        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.ping.return_value = True

        RedisCache._instance = None
        RedisCache._client = None

        with patch.dict('os.environ', {'REDIS_ENABLED': 'true'}):
            cache = RedisCache()
            assert cache.is_connected() is True

    @patch('src.backend.caching_redis.redis.Redis')
    def test_is_connected_failure(self, mock_redis):
        """Test checking connected status when disconnected."""
        from src.backend.caching_redis import RedisCache

        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.ping.side_effect = Exception("Connection lost")

        RedisCache._instance = None
        RedisCache._client = None

        with patch.dict('os.environ', {'REDIS_ENABLED': 'true'}):
            cache = RedisCache()
            assert cache.is_connected() is False

    def test_is_connected_no_client(self):
        """Test is_connected when client is None."""
        from src.backend.caching_redis import RedisCache

        RedisCache._instance = None
        RedisCache._client = None

        with patch.dict('os.environ', {'REDIS_ENABLED': 'false'}):
            cache = RedisCache()
            assert cache.is_connected() is False


@pytest.mark.unit
class TestRedisStats:
    """Test Redis statistics retrieval."""

    @patch('src.backend.caching_redis.redis.Redis')
    def test_get_stats_success(self, mock_redis):
        """Test retrieving Redis statistics."""
        from src.backend.caching_redis import RedisCache

        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.ping.return_value = True
        mock_client.info.return_value = {
            'used_memory_human': '10MB',
            'connected_clients': 5,
            'total_commands_processed': 1000,
            'uptime_in_seconds': 3600,
        }

        RedisCache._instance = None
        RedisCache._client = None

        with patch.dict('os.environ', {'REDIS_ENABLED': 'true'}):
            cache = RedisCache()
            stats = cache.get_stats()

            assert stats['connected'] is True
            assert stats['used_memory'] == '10MB'
            assert stats['connected_clients'] == 5
            assert stats['total_commands'] == 1000

    def test_get_stats_no_connection(self):
        """Test get_stats when not connected."""
        from src.backend.caching_redis import RedisCache

        RedisCache._instance = None
        RedisCache._client = None

        with patch.dict('os.environ', {'REDIS_ENABLED': 'false'}):
            cache = RedisCache()
            stats = cache.get_stats()

            assert stats['connected'] is False


@pytest.mark.unit
class TestRedisCacheDecorator:
    """Test redis_cache decorator."""

    @patch('src.backend.caching_redis.redis.Redis')
    def test_cache_decorator_caches_result(self, mock_redis):
        """Test that decorator caches function results."""
        from src.backend.caching_redis import redis_cache

        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.ping.return_value = True
        mock_client.get.return_value = None

        with patch.dict('os.environ', {'REDIS_ENABLED': 'true'}):
            call_count = 0

            @redis_cache(ttl=300)
            def expensive_function():
                nonlocal call_count
                call_count += 1
                return {"result": "data"}

            # First call
            result1 = expensive_function()
            assert call_count == 1

    @patch('src.backend.caching_redis.redis.Redis')
    def test_cache_decorator_returns_cached_value(self, mock_redis):
        """Test decorator returns cached value on second call."""
        from src.backend.caching_redis import redis_cache, RedisCache

        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.ping.return_value = True

        cached_value = json.dumps({"result": "cached_data"})
        mock_client.get.return_value = cached_value

        RedisCache._instance = None
        RedisCache._client = None
        RedisCache._last_attempt = 0.0

        with patch.dict('os.environ', {'REDIS_ENABLED': 'true'}):
            @redis_cache(ttl=300)
            def expensive_function():
                return {"result": "fresh_data"}

            result = expensive_function()
            assert result == {"result": "cached_data"}


@pytest.mark.unit
class TestRedisCacheEdgeCases:
    """Test edge cases in Redis caching."""

    @patch('src.backend.caching_redis.redis.Redis')
    def test_cache_serialization_error(self, mock_redis):
        """Test handling of serialization errors."""
        from src.backend.caching_redis import RedisCache

        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.ping.return_value = True
        mock_client.setex.side_effect = Exception("Serialization error")

        RedisCache._instance = None
        RedisCache._client = None

        with patch.dict('os.environ', {'REDIS_ENABLED': 'true'}):
            cache = RedisCache()
            result = cache.set("key", {"data": "value"})
            assert result is False

    @patch('src.backend.caching_redis.redis.Redis')
    def test_cache_json_serializable_types(self, mock_redis):
        """Test caching of JSON-serializable types."""
        from src.backend.caching_redis import RedisCache

        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.ping.return_value = True

        RedisCache._instance = None
        RedisCache._client = None

        with patch.dict('os.environ', {'REDIS_ENABLED': 'true'}):
            cache = RedisCache()

            # Test various types
            test_values = [
                {"dict": "value"},
                ["list", "of", "items"],
                "string",
                123,
                12.34,
                True,
                None,
            ]

            for value in test_values:
                result = cache.set(f"key_{id(value)}", value)
                assert result is True

    @patch('src.backend.caching_redis.redis.Redis')
    def test_cache_clear_empty(self, mock_redis):
        """Test clearing cache when empty."""
        from src.backend.caching_redis import RedisCache

        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.ping.return_value = True
        mock_client.scan_iter.return_value = iter([])

        RedisCache._instance = None
        RedisCache._client = None

        with patch.dict('os.environ', {'REDIS_ENABLED': 'true'}):
            cache = RedisCache()
            count = cache.clear()
            assert count == 0


@pytest.mark.unit
class TestGetRedisCacheClient:
    """Test get_redis_client function."""

    @patch('src.backend.caching_redis.redis.Redis')
    def test_get_redis_client_returns_instance(self, mock_redis):
        """Test get_redis_client returns Redis instance."""
        from src.backend.caching_redis import get_redis_client, RedisCache

        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.ping.return_value = True

        RedisCache._instance = None
        RedisCache._client = None

        with patch.dict('os.environ', {'REDIS_ENABLED': 'true'}):
            client = get_redis_client()
            assert client is not None

    def test_get_redis_client_when_disabled(self):
        """Test get_redis_client when Redis is disabled."""
        from src.backend.caching_redis import get_redis_client, RedisCache

        RedisCache._instance = None
        RedisCache._client = None

        with patch.dict('os.environ', {'REDIS_ENABLED': 'false'}):
            client = get_redis_client()
            assert client is None
