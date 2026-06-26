"""
Request ID middleware for the High School Management System API.

This module provides:
    - Unique request ID generation (UUID) for each request
    - X-Request-ID header in responses for traceability
    - Request ID propagation to logging context

Usage:
    >>> from request_id import RequestIDMiddleware
    >>> app.add_middleware(RequestIDMiddleware)
"""

import uuid
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RequestIDMiddleware:
    """ASGI middleware that adds a unique request ID to each request."""

    HEADER_NAME = "X-Request-ID"

    async def __call__(self, scope, receive, send):
        """Add request ID to response headers."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = None

        for header_name, header_value in scope.get("headers", []):
            if header_name.decode() == self.HEADER_NAME.lower():
                request_id = header_value.decode()
                break

        if not request_id:
            request_id = str(uuid.uuid4())

        scope["request_id"] = request_id

        async def send_with_request_id(message):
            if message["type"] == "http.response.start":
                headers = message.get("headers", [])
                headers.append(
                    (self.HEADER_NAME.encode(), request_id.encode())
                )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_request_id)

    def __init__(self, app):
        self.app = app
