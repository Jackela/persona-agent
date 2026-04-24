"""Structured logging configuration for Persona Agent."""

import contextvars
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Context variable for correlation ID
_correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default="unknown"
)


class CorrelationIdFilter(logging.Filter):
    """Filter that adds correlation_id to log records.

    Uses a ContextVar so the correlation ID is propagated across
    async boundaries without explicit passing.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation_id to the log record."""
        record.correlation_id = _correlation_id_var.get()
        return True


def set_correlation_id(correlation_id: str) -> None:
    """Set the current correlation ID in the context variable.

    Args:
        correlation_id: The correlation ID to set
    """
    _correlation_id_var.set(correlation_id)


def get_correlation_id() -> str:
    """Get the current correlation ID from the context variable.

    Returns:
        Current correlation ID or "unknown" if not set
    """
    return _correlation_id_var.get()


def clear_correlation_id() -> None:
    """Reset the correlation ID to the default value."""
    _correlation_id_var.set("unknown")


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging.

    Outputs log records as JSON objects for easy parsing and analysis.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_obj = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if present
        if hasattr(record, "extra"):
            log_obj.update(record.extra)

        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, ensure_ascii=False)


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output.

    Adds ANSI color codes to log messages based on severity level.
    """

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def __init__(self, fmt: str | None = None, use_colors: bool = True):
        super().__init__(fmt)
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        """Format with colors."""
        if self.use_colors and sys.stderr.isatty():
            color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
            reset = self.COLORS["RESET"]
            record.levelname = f"{color}{record.levelname}{reset}"

        return super().format(record)


def setup_logging(
    level: str = "INFO",
    json_format: bool = False,
    log_file: Path | str | None = None,
) -> None:
    """Configure structured logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: If True, output JSON; otherwise, human-readable format
        log_file: Optional path to log file
    """
    # Remove existing handlers
    root = logging.getLogger()
    root.handlers.clear()

    # Set level
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root.setLevel(numeric_level)

    # Correlation ID filter (applied to all handlers)
    correlation_filter = CorrelationIdFilter()

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(numeric_level)
    console_handler.addFilter(correlation_filter)

    if json_format:
        console_handler.setFormatter(JSONFormatter())
    else:
        fmt = "%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] - %(message)s"
        console_handler.setFormatter(ColoredFormatter(fmt))

    root.addHandler(console_handler)

    # File handler if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(numeric_level)
        file_handler.addFilter(correlation_filter)
        file_handler.setFormatter(JSONFormatter())
        root.addHandler(file_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def log_with_extra(
    logger: logging.Logger,
    level: int,
    message: str,
    **kwargs: Any,
) -> None:
    """Log with additional structured data.

    Args:
        logger: Logger instance
        level: Log level
        message: Log message
        **kwargs: Additional fields to include in log
    """
    extra = {"extra": kwargs}
    logger.log(level, message, extra=extra)
