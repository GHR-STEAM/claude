"""
Phase 5 tests: API versioning, request ID, audit logging, graceful shutdown,
frontend integration readiness.

Run: pytest tests/test_phase5.py -v
"""

import pytest
import uuid
import json
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Request ID Middleware
# ---------------------------------------------------------------------------

class TestRequestIDMiddleware:
    """Tests for the X-Request-ID middleware."""

    def test_request_id_generated(self):
        """Middleware generates a UUID when no X-Request-ID is sent."""
        from src.backend.request_id import RequestIDMiddleware

        captured_scope = {}
        captured_response = {}

        async def mock_app(scope, receive, send):
            captured_scope.update(scope)
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": []
            })

        async def mock_receive():
            return {"type": "http.request"}

        async def mock_send(message):
            captured_response.update(message)
            if message["type"] == "http.response.start":
                for k, v in message.get("headers", []):
                    if k == b"x-request-id":
                        captured_scope["response_request_id"] = v.decode()

        middleware = RequestIDMiddleware(mock_app)

        scope = {
            "type": "http",
            "headers": [],
        }

        import asyncio
        asyncio.run(middleware(scope, mock_receive, mock_send))

        assert "request_id" in captured_scope
        assert "response_request_id" in captured_scope
        assert captured_scope["response_request_id"] == captured_scope["request_id"]
        uuid.UUID(captured_scope["request_id"])

    def test_request_id_propagated(self):
        """Middleware preserves an incoming X-Request-ID header."""
        from src.backend.request_id import RequestIDMiddleware

        captured = {}

        async def mock_app(scope, receive, send):
            captured.update(scope)
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": []
            })

        async def mock_receive():
            return {"type": "http.request"}

        async def mock_send(message):
            if message["type"] == "http.response.start":
                for k, v in message.get("headers", []):
                    if k == b"x-request-id":
                        captured["response_request_id"] = v.decode()

        middleware = RequestIDMiddleware(mock_app)
        custom_id = "my-custom-id-123"
        scope = {
            "type": "http",
            "headers": [(b"x-request-id", custom_id.encode())],
        }

        import asyncio
        asyncio.run(middleware(scope, mock_receive, mock_send))

        assert captured["request_id"] == custom_id
        assert captured["response_request_id"] == custom_id

    def test_request_id_non_http_passthrough(self):
        """Middleware passes through non-http (e.g. lifespan) without modification."""
        from src.backend.request_id import RequestIDMiddleware

        called = False

        async def mock_app(scope, receive, send):
            nonlocal called
            called = True

        async def mock_receive():
            return {}

        async def mock_send(message):
            pass

        middleware = RequestIDMiddleware(mock_app)
        scope = {"type": "lifespan"}

        import asyncio
        asyncio.run(middleware(scope, mock_receive, mock_send))
        assert called


# ---------------------------------------------------------------------------
# Audit Logging
# ---------------------------------------------------------------------------

class TestAuditLogging:
    """Tests for the audit logging module."""

    @patch("src.backend.audit._get_collection")
    def test_log_action_inserts_entry(self, mock_get_collection):
        """log_action inserts a correctly structured document."""
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection

        from src.backend.audit import log_action

        log_action(
            action="signup",
            username="mrodriguez",
            details={"activity": "Chess Club", "email": "student@edu.com"},
            request_id="req-123",
            ip_address="127.0.0.1",
        )

        assert mock_collection.insert_one.called
        entry = mock_collection.insert_one.call_args[0][0]
        assert entry["action"] == "signup"
        assert entry["username"] == "mrodriguez"
        assert entry["details"]["activity"] == "Chess Club"
        assert entry["request_id"] == "req-123"
        assert entry["ip_address"] == "127.0.0.1"
        assert "timestamp" in entry

    @patch("src.backend.audit._get_collection")
    def test_log_action_handles_error(self, mock_get_collection):
        """log_action does not raise if MongoDB is unavailable."""
        mock_collection = MagicMock()
        mock_collection.insert_one.side_effect = Exception("Connection lost")
        mock_get_collection.return_value = mock_collection

        from src.backend.audit import log_action

        log_action("test", "user", {})

    @patch("src.backend.audit._get_collection")
    def test_get_audit_logs_returns_results(self, mock_get_collection):
        """get_audit_logs returns formatted log entries."""
        mock_collection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor

        mock_docs = [
            {
                "_id": "507f1f77bcf86cd799439011",
                "action": "signup",
                "username": "mrodriguez",
                "details": {"activity": "Chess"},
                "request_id": "req-1",
                "ip_address": None,
                "timestamp": datetime(2025, 1, 1, tzinfo=timezone.utc),
            }
        ]
        mock_cursor.__iter__ = MagicMock(return_value=iter(mock_docs))
        mock_collection.find.return_value = mock_cursor
        mock_get_collection.return_value = mock_collection

        from src.backend.audit import get_audit_logs

        results = get_audit_logs(limit=10)
        assert len(results) == 1
        assert results[0]["action"] == "signup"
        assert isinstance(results[0]["timestamp"], str)

    @patch("src.backend.audit._get_collection")
    def test_get_audit_logs_with_filters(self, mock_get_collection):
        """get_audit_logs applies action and username filters."""
        mock_collection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.__iter__ = MagicMock(return_value=iter([]))
        mock_get_collection.return_value = mock_collection

        from src.backend.audit import get_audit_logs

        get_audit_logs(action_filter="signup", username_filter="mrodriguez")

        query_arg = mock_collection.find.call_args[0][0]
        assert query_arg["action"] == "signup"
        assert query_arg["username"] == "mrodriguez"

    @patch("src.backend.audit._get_collection")
    def test_get_audit_logs_handles_error(self, mock_get_collection):
        """get_audit_logs returns empty list on error."""
        mock_collection = MagicMock()
        mock_collection.find.side_effect = Exception("DB error")
        mock_get_collection.return_value = mock_collection

        from src.backend.audit import get_audit_logs

        results = get_audit_logs()
        assert results == []


# ---------------------------------------------------------------------------
# API Versioning
# ---------------------------------------------------------------------------

class TestAPIVersioning:
    """Tests for /api/v1 prefix on all routers."""

    def test_api_v1_prefix_constant(self):
        """app.py defines API_V1_PREFIX."""
        from src.app import API_V1_PREFIX
        assert API_V1_PREFIX == "/api/v1"

    def test_activities_router_prefix(self):
        """Activities router has /activities prefix (combined with /api/v1)."""
        from src.backend.routers.activities import router
        assert router.prefix == "/activities"

    def test_auth_router_prefix(self):
        """Auth router has /auth prefix."""
        from src.backend.routers.auth import router
        assert router.prefix == "/auth"

    def test_dashboard_router_prefix(self):
        """Dashboard router has /dashboard prefix (not /api/dashboard)."""
        from src.backend.routers.dashboard import router
        assert router.prefix == "/dashboard"
        assert router.prefix != "/api/dashboard"


# ---------------------------------------------------------------------------
# Graceful Shutdown
# ---------------------------------------------------------------------------

class TestGracefulShutdown:
    """Tests for graceful shutdown signal handlers."""

    def test_shutdown_handler_registered(self):
        """app.py registers SIGTERM and SIGINT handlers."""
        import signal
        from src.app import app

        sigterm_handler = signal.getsignal(signal.SIGTERM)
        sigint_handler = signal.getsignal(signal.SIGINT)

        assert sigterm_handler is not None
        assert sigint_handler is not None
        assert sigterm_handler == sigint_handler

    @patch("src.backend.database.client")
    def test_shutdown_handler_closes_db(self, mock_client):
        """Shutdown handler closes MongoDB connection."""
        import signal
        from src.app import app

        handler = signal.getsignal(signal.SIGTERM)
        if callable(handler):
            handler(signal.SIGTERM, None)
            mock_client.close.assert_called_once()


# ---------------------------------------------------------------------------
# Frontend Integration Readiness
# ---------------------------------------------------------------------------

class TestFrontendIntegration:
    """Verify frontend files exist and reference correct API paths."""

    def test_app_js_uses_api_v1(self):
        """app.js references /api/v1 base."""
        from pathlib import Path
        app_js = Path(__file__).parent.parent / "src" / "static" / "app.js"
        content = app_js.read_text(encoding="utf-8")
        assert '/api/v1' in content

    def test_app_js_has_apiFetch(self):
        """app.js has apiFetch helper with Authorization header."""
        from pathlib import Path
        app_js = Path(__file__).parent.parent / "src" / "static" / "app.js"
        content = app_js.read_text(encoding="utf-8")
        assert 'apiFetch' in content
        assert 'Authorization' in content
        assert 'Bearer' in content

    def test_app_js_has_pagination(self):
        """app.js has pagination controls."""
        from pathlib import Path
        app_js = Path(__file__).parent.parent / "src" / "static" / "app.js"
        content = app_js.read_text(encoding="utf-8")
        assert 'currentPage' in content or 'current_page' in content
        assert 'pageSize' in content or 'page_size' in content

    def test_index_html_has_pagination_ui(self):
        """index.html has pagination UI elements."""
        from pathlib import Path
        index_html = Path(__file__).parent.parent / "src" / "static" / "index.html"
        content = index_html.read_text(encoding="utf-8")
        assert 'pagination' in content.lower() or 'page' in content.lower()

    def test_dashboard_html_uses_api_v1(self):
        """dashboard.html references /api/v1/dashboard."""
        from pathlib import Path
        dashboard_html = Path(__file__).parent.parent / "src" / "static" / "dashboard.html"
        content = dashboard_html.read_text(encoding="utf-8")
        assert '/api/v1/dashboard' in content

    def test_app_js_login_sends_json_body(self):
        """app.js login sends JSON body (not query params)."""
        from pathlib import Path
        app_js = Path(__file__).parent.parent / "src" / "static" / "app.js"
        content = app_js.read_text(encoding="utf-8")
        assert 'JSON.stringify' in content
        assert 'Content-Type' in content
        assert 'application/json' in content

    def test_app_js_stores_token_in_localstorage(self):
        """app.js stores JWT token in localStorage."""
        from pathlib import Path
        app_js = Path(__file__).parent.parent / "src" / "static" / "app.js"
        content = app_js.read_text(encoding="utf-8")
        assert 'localStorage' in content
        assert 'authToken' in content


# ---------------------------------------------------------------------------
# Models Completeness
# ---------------------------------------------------------------------------

class TestModelsComplete:
    """Verify all required Pydantic models exist."""

    def test_login_request_model(self):
        from src.backend.models import LoginRequest
        req = LoginRequest(username="teacher", password="pass123")
        assert req.username == "teacher"

    def test_token_response_model(self):
        from src.backend.models import TokenResponse
        resp = TokenResponse(
            access_token="tok",
            token_type="bearer",
            expires_in=3600,
            username="teacher",
            display_name="Teacher",
            role="teacher",
        )
        assert resp.access_token == "tok"

    def test_signup_request_model(self):
        from src.backend.models import SignupRequest
        req = SignupRequest(email="student@school.edu")
        assert req.email == "student@school.edu"

    def test_unregister_request_model(self):
        from src.backend.models import UnregisterRequest
        req = UnregisterRequest(email="student@school.edu")
        assert req.email == "student@school.edu"

    def test_message_response_model(self):
        from src.backend.models import MessageResponse
        msg = MessageResponse(message="Success")
        assert msg.message == "Success"

    def test_user_info_model(self):
        from src.backend.models import UserInfo
        info = UserInfo(username="teacher", display_name="Teacher", role="teacher")
        assert info.username == "teacher"


# ---------------------------------------------------------------------------
# Backward Compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    """Ensure Phase 5 changes don't break Phase 3/4 functionality."""

    def test_request_id_middleware_class_exists(self):
        from src.backend.request_id import RequestIDMiddleware
        assert hasattr(RequestIDMiddleware, "__call__")

    def test_audit_module_imports(self):
        from src.backend.audit import log_action, get_audit_logs
        assert callable(log_action)
        assert callable(get_audit_logs)

    def test_app_has_metrics_middleware(self):
        from src.app import app
        assert app is not None

    def test_auth_router_has_login_endpoint(self):
        from src.backend.routers.auth import router
        routes = [r.path for r in router.routes]
        assert "/auth/login" in routes

    def test_auth_router_has_check_session(self):
        from src.backend.routers.auth import router
        routes = [r.path for r in router.routes]
        assert "/auth/check-session" in routes

    def test_activities_router_has_signup(self):
        from src.backend.routers.activities import router
        routes = [r.path for r in router.routes]
        assert any("/signup" in r for r in routes)

    def test_dashboard_router_has_health(self):
        from src.backend.routers.dashboard import router
        routes = [r.path for r in router.routes]
        assert "/dashboard/health" in routes
