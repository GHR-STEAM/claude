"""
High School Management System API

A FastAPI application that allows students and teachers to view and manage
extracurricular activities at Mergington High School.

Features:
    - User authentication with secure password hashing (Argon2)
    - Activity browsing and filtering by day, time, and category
    - Student registration management
    - Teacher dashboard for managing activity enrollment
    - Role-based access control (teacher/admin)
    - Security hardening with CORS, Rate Limiting, and input validation

Security:
    - CORS protection with configurable origins
    - Rate limiting on authentication endpoints
    - Input validation and sanitization
    - Password hashing using Argon2
    - Environment-based configuration

Database:
    - MongoDB for persistent data storage
    - Structured schema for activities and teachers
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv
import os
from pathlib import Path
from .backend import routers, database
from .backend.security import limiter, handle_rate_limit_exceeded
from .backend.logging_config import setup_logging, RequestLogger
from .backend.performance import init_performance
from .backend.metrics import MetricsMiddleware, metrics_collector
from .backend.query_optimization import init_indexes
from .backend.error_handlers import register_error_handlers
from .backend.request_id import RequestIDMiddleware

API_V1_PREFIX = "/api/v1"

# Load environment variables before reading them
load_dotenv()

def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application with security middleware.

    Returns:
        FastAPI: Configured application instance with all middleware and routes

    Raises:
        ValueError: If environment configuration is invalid
    """
    # Initialize web host
    app = FastAPI(
        title="Mergington High School API",
        description="API for viewing and signing up for extracurricular activities",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json"
    )

    # Rate limiting setup
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, handle_rate_limit_exceeded)

    # Register global error handlers
    register_error_handlers(app)

    # Security: Add CORS middleware with restricted origins
    cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # Security: Add Trusted Host middleware with configurable hosts
    allowed_hosts = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    # Initialize database with sample data if empty
    database.init_database()

    # Initialize performance optimizations
    init_performance()

    # Initialize database indexes
    try:
        init_indexes(database.db)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Index initialization failed: {e}")

    # Add request logging middleware
    app.add_middleware(RequestLogger)

    # Add request ID middleware
    app.add_middleware(RequestIDMiddleware)

    # Add metrics collection middleware
    app.add_middleware(MetricsMiddleware, collector=metrics_collector)

    # Mount the static files directory for serving the frontend
    current_dir = Path(__file__).parent
    app.mount("/static", StaticFiles(directory=os.path.join(current_dir, "static")), name="static")

    # Root endpoint to redirect to static index.html
    @app.get("/")
    def root():
        """Redirect root path to the frontend application."""
        return RedirectResponse(url="/static/index.html")

    # Dashboard monitoring page
    @app.get("/dashboard")
    def dashboard_page():
        """Serve the monitoring dashboard page."""
        return RedirectResponse(url="/static/dashboard.html")

    # Include routers under /api/v1 prefix
    app.include_router(routers.activities.router, prefix=API_V1_PREFIX)
    app.include_router(routers.auth.router, prefix=API_V1_PREFIX)
    app.include_router(routers.dashboard.router, prefix=API_V1_PREFIX)
    app.include_router(routers.analytics.router, prefix=API_V1_PREFIX)
    app.include_router(routers.backup.router, prefix=API_V1_PREFIX)
    app.include_router(routers.advanced_cache.router, prefix=API_V1_PREFIX)

    return app


def _register_shutdown(app: FastAPI):
    """Register graceful shutdown handlers."""
    import signal
    import logging

    logger = logging.getLogger(__name__)

    def shutdown_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        try:
            database.client.close()
            logger.info("MongoDB connection closed")
        except Exception as e:
            logger.error(f"Error closing MongoDB: {e}")
        try:
            from .backend.performance import DatabasePool
            DatabasePool().close()
            logger.info("Database pool closed")
        except Exception:
            pass

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

# Create the application instance
app = create_app()

# Register graceful shutdown
_register_shutdown(app)

# Initialize logging
setup_logging()
