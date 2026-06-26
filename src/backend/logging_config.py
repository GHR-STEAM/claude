"""
Logging configuration for the High School Management System API.

This module provides centralized logging setup with:
    - File rotation
    - Different log levels for console and file
    - Structured logging
    - Request/Response logging

Usage:
    >>> from logging_config import get_logger
    >>> logger = get_logger(__name__)
    >>> logger.info("Application started")
"""

import logging
import logging.handlers
import os
from pathlib import Path
from datetime import datetime

# Create logs directory if it doesn't exist
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Log file configuration
LOG_FILE = LOG_DIR / f"app_{datetime.now().strftime('%Y%m%d')}.log"
ERROR_LOG_FILE = LOG_DIR / f"error_{datetime.now().strftime('%Y%m%d')}.log"

# Log levels from environment
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
FILE_LOG_LEVEL = os.getenv("FILE_LOG_LEVEL", "DEBUG")

# Logging format
DETAILED_FORMAT = (
    "%(asctime)s - %(name)s - %(levelname)s - "
    "[%(filename)s:%(lineno)d] - %(funcName)s() - %(message)s"
)
SIMPLE_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"


def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        logging.Logger: Configured logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("This is an info message")
    """
    logger = logging.getLogger(name)

    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(LOG_LEVEL)
        console_formatter = logging.Formatter(SIMPLE_FORMAT)
        console_handler.setFormatter(console_formatter)

        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,  # Keep 5 backup files
        )
        file_handler.setLevel(FILE_LOG_LEVEL)
        file_formatter = logging.Formatter(DETAILED_FORMAT)
        file_handler.setFormatter(file_formatter)

        # Error file handler
        error_handler = logging.handlers.RotatingFileHandler(
            ERROR_LOG_FILE,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)

        # Add handlers
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        logger.addHandler(error_handler)

    return logger


def setup_logging():
    """
    Initialize logging for the entire application.

    This should be called once at application startup.
    """
    root_logger = get_logger("mergington_api")
    root_logger.info("=" * 60)
    root_logger.info("Application Started")
    root_logger.info(f"Log Level: {LOG_LEVEL}")
    root_logger.info(f"Log Directory: {LOG_DIR.absolute()}")
    root_logger.info("=" * 60)


class RequestLogger:
    """Middleware for logging HTTP requests and responses."""

    def __init__(self, app):
        self.app = app
        self.logger = get_logger(__name__)

    async def __call__(self, scope, receive, send):
        """Log incoming requests."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "")

        self.logger.info(f"Incoming Request: {method} {path}")

        async def send_with_logging(message):
            if message["type"] == "http.response.start":
                status_code = message.get("status", "unknown")
                self.logger.info(f"Response: {status_code} for {method} {path}")
            await send(message)

        await self.app(scope, receive, send_with_logging)
