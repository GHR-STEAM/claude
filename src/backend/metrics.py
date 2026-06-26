"""
Advanced metrics middleware for the High School Management System API.

This module provides:
    - Request latency tracking (p50, p95, p99 percentiles)
    - HTTP status code counters
    - Request count tracking
    - Time-windowed metrics collection
    - Metrics snapshot endpoint integration

Usage:
    >>> from metrics import MetricsCollector, MetricsMiddleware
    >>> collector = MetricsCollector()
    >>> app.add_middleware(MetricsMiddleware, collector=collector)
"""

import time
import threading
from collections import defaultdict, deque
from typing import Dict, Any, Optional, Deque
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Thread-safe collector for request metrics with time-windowed storage."""

    def __init__(self, window_seconds: int = 300, max_requests: int = 10000):
        """
        Initialize the metrics collector.

        Args:
            window_seconds: Time window for keeping request data (default: 300s = 5 min)
            max_requests: Maximum number of request records to keep in memory
        """
        self._lock = threading.Lock()
        self._window_seconds = window_seconds
        self._max_requests = max_requests

        self._latencies: Deque[tuple] = deque()
        self._status_counts: Dict[int, int] = defaultdict(int)
        self._endpoint_counts: Dict[str, int] = defaultdict(int)
        self._total_requests = 0
        self._error_count = 0
        self._start_time = time.time()

    def record_request(self, method: str, path: str, status_code: int, latency: float):
        """
        Record a single request's metrics.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path
            status_code: HTTP status code
            latency: Response time in seconds
        """
        now = time.time()
        endpoint = f"{method} {path}"

        with self._lock:
            self._latencies.append((now, latency))
            self._status_counts[status_code] += 1
            self._endpoint_counts[endpoint] += 1
            self._total_requests += 1
            if status_code >= 400:
                self._error_count += 1

            self._cleanup(now)

    def _cleanup(self, now: float):
        """Remove entries outside the time window and enforce max size."""
        cutoff = now - self._window_seconds
        while self._latencies and self._latencies[0][0] < cutoff:
            self._latencies.popleft()

        if len(self._latencies) > self._max_requests:
            excess = len(self._latencies) - self._max_requests
            for _ in range(excess):
                self._latencies.popleft()

    def _percentile(self, sorted_values: list, pct: float) -> float:
        """Calculate the percentile from sorted values."""
        if not sorted_values:
            return 0.0
        index = int(len(sorted_values) * pct / 100)
        if index >= len(sorted_values):
            index = len(sorted_values) - 1
        return sorted_values[index]

    def get_snapshot(self) -> Dict[str, Any]:
        """
        Get a snapshot of current metrics.

        Returns:
            dict: Current metrics including latency percentiles, status counts, and totals
        """
        with self._lock:
            latencies = [l for _, l in self._latencies]
            latencies_sorted = sorted(latencies)

            uptime = time.time() - self._start_time
            avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "uptime_seconds": round(uptime, 2),
                "total_requests": self._total_requests,
                "requests_in_window": len(latencies),
                "error_count": self._error_count,
                "error_rate": round(self._error_count / self._total_requests * 100, 2)
                if self._total_requests > 0
                else 0.0,
                "latency": {
                    "avg_ms": round(avg_latency * 1000, 2),
                    "p50_ms": round(self._percentile(latencies_sorted, 50) * 1000, 2),
                    "p95_ms": round(self._percentile(latencies_sorted, 95) * 1000, 2),
                    "p99_ms": round(self._percentile(latencies_sorted, 99) * 1000, 2),
                    "min_ms": round(min(latencies) * 1000, 2) if latencies else 0.0,
                    "max_ms": round(max(latencies) * 1000, 2) if latencies else 0.0,
                },
                "status_codes": dict(self._status_counts),
                "top_endpoints": dict(
                    sorted(
                        self._endpoint_counts.items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )[:10]
                ),
            }

    def reset(self):
        """Reset all collected metrics."""
        with self._lock:
            self._latencies.clear()
            self._status_counts.clear()
            self._endpoint_counts.clear()
            self._total_requests = 0
            self._error_count = 0
            self._start_time = time.time()
            logger.info("Metrics collector reset")


metrics_collector = MetricsCollector()


class MetricsMiddleware:
    """ASGI middleware for collecting request metrics."""

    def __init__(self, app, collector: Optional[MetricsCollector] = None):
        """
        Initialize the metrics middleware.

        Args:
            app: The ASGI application
            collector: Optional custom MetricsCollector instance
        """
        self.app = app
        self.collector = collector or metrics_collector

    async def __call__(self, scope, receive, send):
        """Collect metrics for each HTTP request."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        path = scope.get("path", "")
        start_time = time.time()
        status_code = 500

        async def send_with_metrics(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 500)
            await send(message)

        try:
            await self.app(scope, receive, send_with_metrics)
        finally:
            latency = time.time() - start_time
            self.collector.record_request(method, path, status_code, latency)
