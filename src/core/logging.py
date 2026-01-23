"""Logging configuration helper for SEC EDGAR 10-K fetcher.

Provides a centralized logging setup to ensure consistent logging across all modules.
"""

import logging
import sys
from typing import Optional

# Default format for log messages
DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Package root logger name
PACKAGE_LOGGER_NAME = "src"


def setup_logging(
    level: int = logging.INFO,
    log_format: Optional[str] = None,
    date_format: Optional[str] = None,
) -> None:
    """Configure logging for the application.

    Sets up the root logger for the 'src' package with appropriate formatting.
    Should be called once at application startup (in main.py or cli.py).

    Args:
        level: Logging level (default: logging.INFO).
        log_format: Custom log format string (default: DEFAULT_FORMAT).
        date_format: Custom date format string (default: DEFAULT_DATE_FORMAT).

    Example:
        from src.core.logging import setup_logging
        setup_logging(level=logging.DEBUG)
    """
    log_format = log_format or DEFAULT_FORMAT
    date_format = date_format or DEFAULT_DATE_FORMAT

    # Create handler for stderr
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)

    # Create formatter
    formatter = logging.Formatter(fmt=log_format, datefmt=date_format)
    handler.setFormatter(formatter)

    # Configure the package root logger
    package_logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    package_logger.setLevel(level)

    # Remove any existing handlers to avoid duplicates
    package_logger.handlers.clear()
    package_logger.addHandler(handler)

    # Prevent propagation to root logger to avoid duplicate logs
    package_logger.propagate = False

    # Log the setup at DEBUG level
    package_logger.debug("Logging configured: level=%s", logging.getLevelName(level))


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific module.

    Returns a logger that is a child of the package root logger,
    ensuring consistent configuration across all modules.

    Args:
        name: The module name (typically __name__).

    Returns:
        A configured logger instance.

    Example:
        from src.core.logging import get_logger
        logger = get_logger(__name__)
        logger.info("Processing company: %s", ticker)
    """
    return logging.getLogger(name)


def set_level(level: int) -> None:
    """Change the logging level at runtime.

    Args:
        level: New logging level (e.g., logging.DEBUG, logging.WARNING).
    """
    package_logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    package_logger.setLevel(level)
    for handler in package_logger.handlers:
        handler.setLevel(level)
