"""
Global error handling middleware for the High School Management System API.

This module provides:
    - Centralized exception handler for unhandled errors
    - Sanitized error responses (no stack traces in production)
    - Structured error logging
    - Consistent error response format

Usage:
    >>> from error_handlers import register_error_handlers
    >>> register_error_handlers(app)
"""

import logging
import os
import traceback
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from .models import ErrorResponse

logger = logging.getLogger(__name__)

IS_PRODUCTION = os.getenv("ENVIRONMENT", "development").lower() == "production"


def register_error_handlers(app: FastAPI):
    """Register all global error handlers on the FastAPI app.

    Args:
        app: FastAPI application instance
    """

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTPException with consistent format."""
        logger.warning(
            f"HTTP {exc.status_code} on {request.method} {request.url.path}: {exc.detail}"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(detail=exc.detail).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle request validation errors with field details."""
        errors = []
        for err in exc.errors():
            field = ".".join(str(loc) for loc in err.get("loc", []))
            errors.append(f"{field}: {err.get('msg', 'Invalid value')}")

        detail = "; ".join(errors) if errors else "Validation error"
        logger.warning(
            f"Validation error on {request.method} {request.url.path}: {detail}"
        )
        return JSONResponse(
            status_code=422,
            content={
                "detail": detail,
                "error_code": "VALIDATION_ERROR",
                "errors": exc.errors() if not IS_PRODUCTION else None,
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle all unhandled exceptions with sanitized response."""
        logger.error(
            f"Unhandled exception on {request.method} {request.url.path}: {exc}\n"
            f"{traceback.format_exc()}"
        )

        detail = "Internal server error"
        if not IS_PRODUCTION:
            detail = f"{type(exc).__name__}: {str(exc)}"

        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                detail=detail,
                error_code="INTERNAL_ERROR",
            ).model_dump(),
        )
