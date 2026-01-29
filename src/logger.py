"""
Logging Configuration for Kalshi Trading Bot

Provides centralized logging with:
- Console output with color coding
- File output with rotation
- Different log levels for different environments
- Structured logging format
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """
    Custom formatter with color-coded output for console.
    """

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        """Format log record with colors."""
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"

        # Format the message
        formatted = super().format(record)

        # Reset levelname for other handlers
        record.levelname = levelname

        return formatted


def setup_logger(
    name: str = "kalshi_bot",
    log_file: Optional[str] = None,
    level: str = "INFO",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    console_output: bool = True,
    file_output: bool = True,
) -> logging.Logger:
    """
    Set up and configure logger with console and file handlers.

    Args:
        name: Logger name
        log_file: Path to log file (default: logs/{name}.log)
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        max_bytes: Maximum log file size before rotation (default: 10MB)
        backup_count: Number of backup log files to keep (default: 5)
        console_output: Enable console output (default: True)
        file_output: Enable file output (default: True)

    Returns:
        Configured logger instance

    Example:
        >>> logger = setup_logger(name="my_bot", level="DEBUG")
        >>> logger.info("Bot started")
        >>> logger.error("An error occurred", exc_info=True)
    """

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_formatter = ColoredFormatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S"
    )

    # Console handler with colors
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    # File handler with rotation
    if file_output:
        # Set default log file path
        if log_file is None:
            log_file = f"logs/{name}.log"

        # Create logs directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    # Log initial setup message
    logger.info("=" * 80)
    logger.info(f"Logger initialized: {name}")
    logger.info(f"Log level: {level.upper()}")
    if file_output:
        logger.info(f"Log file: {log_file}")
    logger.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get an existing logger by name.

    Args:
        name: Logger name

    Returns:
        Logger instance

    Example:
        >>> logger = get_logger("kalshi_bot")
        >>> logger.info("Using existing logger")
    """
    return logging.getLogger(name)


def set_log_level(logger: logging.Logger, level: str):
    """
    Change log level for an existing logger.

    Args:
        logger: Logger instance
        level: New log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Example:
        >>> logger = get_logger("kalshi_bot")
        >>> set_log_level(logger, "DEBUG")
    """
    logger.setLevel(getattr(logging, level.upper()))
    logger.info(f"Log level changed to: {level.upper()}")


class LoggerContextManager:
    """
    Context manager for temporary log level changes.

    Example:
        >>> logger = setup_logger("my_bot", level="INFO")
        >>> with LoggerContextManager(logger, "DEBUG"):
        ...     logger.debug("This debug message will be shown")
        >>> logger.debug("This debug message will NOT be shown")
    """

    def __init__(self, logger: logging.Logger, temp_level: str):
        self.logger = logger
        self.temp_level = temp_level
        self.original_level = logger.level

    def __enter__(self):
        self.logger.setLevel(getattr(logging, self.temp_level.upper()))
        return self.logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.setLevel(self.original_level)


# Quick setup for common use cases
def setup_debug_logger(name: str = "kalshi_bot") -> logging.Logger:
    """Quick setup for debug-level logging."""
    return setup_logger(name=name, level="DEBUG")


def setup_production_logger(
    name: str = "kalshi_bot", log_file: str = "logs/production.log"
) -> logging.Logger:
    """Quick setup for production logging (INFO level, file only)."""
    return setup_logger(
        name=name,
        log_file=log_file,
        level="INFO",
        console_output=False,
        file_output=True,
    )


def setup_silent_logger(name: str = "kalshi_bot") -> logging.Logger:
    """Quick setup for minimal logging (WARNING level only)."""
    return setup_logger(
        name=name, level="WARNING", console_output=True, file_output=False
    )


# Example usage and testing
if __name__ == "__main__":
    # Test the logger
    print("Testing logger setup...")

    # Create logger
    logger = setup_logger(name="test_bot", log_file="logs/test.log", level="DEBUG")

    # Test different log levels
    logger.debug("This is a DEBUG message")
    logger.info("This is an INFO message")
    logger.warning("This is a WARNING message")
    logger.error("This is an ERROR message")
    logger.critical("This is a CRITICAL message")

    # Test exception logging
    try:
        result = 1 / 0
    except ZeroDivisionError:
        logger.error("Caught an exception!", exc_info=True)

    # Test context manager
    print("--- Testing temporary DEBUG mode ---")
    logger = setup_logger("test_bot2", level="INFO")
    logger.debug("This debug message will NOT show")

    with LoggerContextManager(logger, "DEBUG"):
        logger.debug("This debug message WILL show (temporary DEBUG mode)")

    logger.debug("This debug message will NOT show again")

    print("✅ Logger tests complete! Check logs/test.log")
