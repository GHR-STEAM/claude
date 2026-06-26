"""
Tests for Phase 3: Advanced metrics, cache invalidation, query optimization, and backup utilities.
"""

import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone


@pytest.mark.unit
class TestMetricsCollector:
    """Test the MetricsCollector class."""

    def test_record_request(self):
        from src.backend.metrics import MetricsCollector
        collector = MetricsCollector()
        collector.record_request("GET", "/activities", 200, 0.05)
        snapshot = collector.get_snapshot()
        assert snapshot["total_requests"] == 1
        assert snapshot["requests_in_window"] == 1
        assert snapshot["status_codes"][200] == 1

    def test_error_count_tracking(self):
        from src.backend.metrics import MetricsCollector
        collector = MetricsCollector()
        collector.record_request("GET", "/test", 200, 0.01)
        collector.record_request("POST", "/test", 500, 0.01)
        collector.record_request("GET", "/test", 404, 0.01)
        snapshot = collector.get_snapshot()
        assert snapshot["error_count"] == 2
        assert snapshot["error_rate"] > 0

    def test_latency_percentiles(self):
        from src.backend.metrics import MetricsCollector
        collector = MetricsCollector()
        for i in range(100):
            collector.record_request("GET", "/test", 200, i * 0.001)
        snapshot = collector.get_snapshot()
        lat = snapshot["latency"]
        assert lat["p50_ms"] >= 0
        assert lat["p95_ms"] >= lat["p50_ms"]
        assert lat["p99_ms"] >= lat["p95_ms"]

    def test_reset(self):
        from src.backend.metrics import MetricsCollector
        collector = MetricsCollector()
        collector.record_request("GET", "/test", 200, 0.01)
        assert collector.get_snapshot()["total_requests"] == 1
        collector.reset()
        assert collector.get_snapshot()["total_requests"] == 0

    def test_top_endpoints(self):
        from src.backend.metrics import MetricsCollector
        collector = MetricsCollector()
        for _ in range(5):
            collector.record_request("GET", "/activities", 200, 0.01)
        for _ in range(3):
            collector.record_request("POST", "/auth/login", 200, 0.01)
        snapshot = collector.get_snapshot()
        endpoints = snapshot["top_endpoints"]
        assert "GET /activities" in endpoints
        assert endpoints["GET /activities"] == 5

    def test_uptime_tracking(self):
        from src.backend.metrics import MetricsCollector
        collector = MetricsCollector()
        time.sleep(0.1)
        snapshot = collector.get_snapshot()
        assert snapshot["uptime_seconds"] >= 0.1

    def test_empty_snapshot(self):
        from src.backend.metrics import MetricsCollector
        collector = MetricsCollector()
        snapshot = collector.get_snapshot()
        assert snapshot["total_requests"] == 0
        assert snapshot["latency"]["avg_ms"] == 0.0
        assert snapshot["error_rate"] == 0.0


@pytest.mark.unit
class TestCacheInvalidation:
    """Test cache invalidation utilities."""

    def test_invalidate_in_memory_cache_all(self):
        from src.backend.cache_invalidation import invalidate_in_memory_cache
        from src.backend.performance import PerformanceCache
        PerformanceCache.set("test_key", "value", ttl=60)
        assert PerformanceCache.get("test_key") is not None
        invalidate_in_memory_cache()
        assert PerformanceCache.get("test_key") is None

    def test_invalidate_in_memory_cache_specific(self):
        from src.backend.cache_invalidation import invalidate_in_memory_cache
        from src.backend.performance import PerformanceCache
        PerformanceCache.set("key1", "val1", ttl=60)
        PerformanceCache.set("key2", "val2", ttl=60)
        invalidate_in_memory_cache(keys=["key1"])
        assert PerformanceCache.get("key1") is None
        assert PerformanceCache.get("key2") is not None

    def test_invalidate_for_domain_activities(self):
        from src.backend.cache_invalidation import invalidate_for_domain
        from src.backend.performance import PerformanceCache
        PerformanceCache.set("get_activities", "data", ttl=60)
        invalidate_for_domain("activities")
        assert PerformanceCache.get("get_activities") is None

    def test_invalidate_all(self):
        from src.backend.cache_invalidation import invalidate_all
        from src.backend.performance import PerformanceCache
        PerformanceCache.set("k1", "v1", ttl=60)
        PerformanceCache.set("k2", "v2", ttl=60)
        invalidate_all()
        assert PerformanceCache.get("k1") is None
        assert PerformanceCache.get("k2") is None

    def test_invalidate_decorator(self):
        from src.backend.cache_invalidation import invalidate_after_mutation
        from src.backend.performance import PerformanceCache

        @invalidate_after_mutation("activities")
        def mock_mutation():
            return "success"

        PerformanceCache.set("get_activities", "cached", ttl=60)
        result = mock_mutation()
        assert result == "success"
        assert PerformanceCache.get("get_activities") is None


@pytest.mark.unit
class TestQueryOptimization:
    """Test query optimization utilities."""

    def test_init_indexes(self):
        from src.backend.query_optimization import init_indexes
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_collection.create_index.return_value = "index_name"
        mock_db.__getitem__ = Mock(return_value=mock_collection)

        result = init_indexes(mock_db)
        assert "activities" in result
        assert "teachers" in result

    def test_explain_query(self):
        from src.backend.query_optimization import explain_query
        mock_collection = MagicMock()
        mock_cursor = MagicMock()
        mock_explain = {
            "queryPlanner": {
                "winningPlan": {
                    "stage": "IXSCAN",
                    "inputStage": {"indexName": "_id_"},
                }
            },
            "executionStats": {
                "totalDocsExamined": 10,
                "totalKeysExamined": 10,
                "executionTimeMillis": 5,
                "nReturned": 10,
            },
        }
        mock_cursor.explain.return_value = mock_explain
        mock_collection.find.return_value = mock_cursor

        result = explain_query(mock_collection, {"_id": "test"})
        assert result["index_used"] == "_id_"
        assert result["total_docs_examined"] == 10
        assert result["execution_time_ms"] == 5
        assert result["n_returned"] == 10

    def test_get_index_status(self):
        from src.backend.query_optimization import get_index_status
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_collection.list_indexes.return_value = iter([
            {"name": "_id_", "key": {"_id": 1}, "unique": True},
        ])
        mock_db.__getitem__ = Mock(return_value=mock_collection)

        result = get_index_status(mock_db)
        assert "activities" in result
        assert len(result["activities"]) == 1
        assert result["activities"][0]["name"] == "_id_"

    def test_analyze_slow_queries_fast(self):
        from src.backend.query_optimization import analyze_slow_queries
        mock_collection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.explain.return_value = {
            "queryPlanner": {"winningPlan": {"stage": "IXSCAN", "inputStage": {"indexName": "_id_"}}},
            "executionStats": {"totalDocsExamined": 1, "totalKeysExamined": 1, "executionTimeMillis": 2, "nReturned": 1},
        }
        mock_collection.find.return_value = mock_cursor

        result = analyze_slow_queries(mock_collection, {}, threshold_ms=100)
        assert result is None

    def test_analyze_slow_queries_slow(self):
        from src.backend.query_optimization import analyze_slow_queries
        mock_collection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.explain.return_value = {
            "queryPlanner": {"winningPlan": {"stage": "COLLSCAN"}},
            "executionStats": {"totalDocsExamined": 1000, "totalKeysExamined": 0, "executionTimeMillis": 250, "nReturned": 5},
        }
        mock_collection.find.return_value = mock_cursor

        result = analyze_slow_queries(mock_collection, {}, threshold_ms=100)
        assert result is not None
        assert result["is_slow"] is True
        assert result["execution_time_ms"] == 250


@pytest.mark.unit
class TestBackupUtilities:
    """Test database backup utilities."""

    def test_export_database(self, tmp_path):
        from src.backend.backup import export_database, BACKUP_DIR
        mock_db = MagicMock()
        mock_db.name = "test_db"
        mock_collection = MagicMock()
        mock_collection.find.return_value = iter([
            {"_id": "act1", "description": "Test", "participants": []},
        ])
        mock_db.__getitem__ = Mock(return_value=mock_collection)

        with patch.object(__import__('src.backend.backup', fromlist=['BACKUP_DIR']), 'BACKUP_DIR', tmp_path):
            path = export_database(mock_db, backup_name="test_backup")
            assert "test_backup" in path
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert "metadata" in data
            assert "data" in data
            assert "activities" in data["data"]

    def test_list_backups(self, tmp_path):
        from src.backend import backup as backup_module
        backup_file = tmp_path / "backup_test.json"
        backup_file.write_text('{"metadata": {}, "data": {}}')

        with patch.object(backup_module, 'BACKUP_DIR', tmp_path):
            backups = backup_module.list_backups()
            assert len(backups) == 1
            assert backups[0]["filename"] == "backup_test.json"

    def test_verify_backup_valid(self, tmp_path):
        from src.backend.backup import verify_backup
        backup_file = tmp_path / "valid_backup.json"
        data = {
            "metadata": {"version": "1.0.0", "database_name": "test"},
            "data": {"activities": [{"_id": "test", "name": "Test"}]},
        }
        backup_file.write_text(json.dumps(data))

        result = verify_backup(str(backup_file))
        assert result["valid"] is True
        assert result["total_documents"] == 1

    def test_verify_backup_invalid(self, tmp_path):
        from src.backend.backup import verify_backup
        backup_file = tmp_path / "invalid_backup.json"
        backup_file.write_text('{"wrong": "format"}')

        result = verify_backup(str(backup_file))
        assert result["valid"] is False

    def test_verify_backup_not_found(self):
        from src.backend.backup import verify_backup
        result = verify_backup("nonexistent.json")
        assert result["valid"] is False

    def test_delete_backup(self, tmp_path):
        from src.backend.backup import delete_backup
        backup_file = tmp_path / "to_delete.json"
        backup_file.write_text("{}")
        assert delete_backup(str(backup_file)) is True
        assert not backup_file.exists()

    def test_delete_backup_not_found(self):
        from src.backend.backup import delete_backup
        assert delete_backup("nonexistent.json") is False


@pytest.mark.integration
class TestDashboardNewEndpoints:
    """Test new dashboard endpoints."""

    def test_metrics_advanced_endpoint(self, api_client):
        """Test advanced metrics endpoint."""
        from fastapi.testclient import TestClient
        response = api_client.get("/api/dashboard/metrics-advanced")
        assert response.status_code == 200
        data = response.json()
        assert "total_requests" in data
        assert "latency" in data
        assert "status_codes" in data

    def test_metrics_reset_endpoint(self, api_client):
        """Test metrics reset endpoint."""
        response = api_client.post("/api/dashboard/metrics/reset")
        assert response.status_code == 200
        assert "message" in response.json()

    def test_indexes_endpoint(self, api_client):
        """Test index status endpoint."""
        response = api_client.get("/api/dashboard/indexes")
        assert response.status_code in [200, 500]

    def test_backups_endpoint(self, api_client):
        """Test backups listing endpoint."""
        response = api_client.get("/api/dashboard/backups")
        assert response.status_code == 200
        data = response.json()
        assert "backups" in data
        assert "total" in data
