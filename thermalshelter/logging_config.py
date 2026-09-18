"""
Logging configuration for Thermal-Shelter.

Provides structured logging with configurable levels for debugging and monitoring.
"""
import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    format_type: str = "simple"
) -> logging.Logger:
    """
    Configure logging for the Thermal-Shelter application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path to write logs to
        format_type: "simple" or "detailed" format

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("thermalshelter")
    logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    logger.handlers.clear()

    # Choose format
    if format_type == "detailed":
        fmt = "%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s"
    else:
        fmt = "%(levelname)s: %(message)s"

    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Module-level logger - can be imported by other modules
logger = logging.getLogger("thermalshelter")
