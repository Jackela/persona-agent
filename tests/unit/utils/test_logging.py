"""Tests for logging_config module."""

import json
import logging
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from persona_agent.utils.logging_config import (
    ColoredFormatter,
    JSONFormatter,
    get_logger,
    log_with_extra,
    setup_logging,
)


class TestJSONFormatter:
    """Tests for JSONFormatter."""

    def test_basic_format(self):
        """Test basic log formatting as JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "INFO"
        assert data["logger"] == "test"
        assert data["message"] == "Test message"
        assert "timestamp" in data

    def test_format_with_extra(self):
        """Test formatting with extra fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.extra = {"user_id": "123", "action": "login"}

        output = formatter.format(record)
        data = json.loads(output)

        assert data["user_id"] == "123"
        assert data["action"] == "login"

    def test_format_with_exception(self):
        """Test formatting with exception info."""
        formatter = JSONFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info(),
            )

        output = formatter.format(record)
        data = json.loads(output)

        assert "exception" in data
        assert "ValueError" in data["exception"]


class TestColoredFormatter:
    """Tests for ColoredFormatter."""

    def test_basic_format_no_tty(self):
        """Test basic formatting without TTY."""
        formatter = ColoredFormatter("%(levelname)s - %(message)s")

        with patch.object(sys.stderr, "isatty", return_value=False):
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg="Test message",
                args=(),
                exc_info=None,
            )

            output = formatter.format(record)
            assert "INFO" in output
            assert "Test message" in output

    def test_format_with_tty(self):
        """Test formatting with TTY adds colors."""
        formatter = ColoredFormatter("%(levelname)s - %(message)s")

        with patch.object(sys.stderr, "isatty", return_value=True):
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error message",
                args=(),
                exc_info=None,
            )

            output = formatter.format(record)
            # ANSI color codes should be present
            assert "\033[" in output
            assert "ERROR" in output

    def test_format_colors_disabled(self):
        """Test formatting with colors disabled."""
        formatter = ColoredFormatter("%(levelname)s - %(message)s", use_colors=False)

        with patch.object(sys.stderr, "isatty", return_value=True):
            record = logging.LogRecord(
                name="test",
                level=logging.WARNING,
                pathname="test.py",
                lineno=1,
                msg="Warning message",
                args=(),
                exc_info=None,
            )

            output = formatter.format(record)
            # No ANSI color codes
            assert "\033[" not in output


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_basic_logging(self):
        """Test basic logging setup."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_root = MagicMock()
            mock_get_logger.return_value = mock_root

            setup_logging(level="INFO")

            mock_root.handlers.clear.assert_called_once()
            mock_root.setLevel.assert_called_with(logging.INFO)
            assert mock_root.addHandler.called

    def test_setup_logging_invalid_level(self):
        """Test setup with invalid level defaults to INFO."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_root = MagicMock()
            mock_get_logger.return_value = mock_root

            setup_logging(level="INVALID")

            mock_root.setLevel.assert_called_with(logging.INFO)

    def test_setup_logging_json_format(self):
        """Test setup with JSON formatting."""
        with patch("logging.getLogger") as mock_get_logger:
            with patch("persona_agent.utils.logging_config.JSONFormatter") as mock_json_formatter:
                mock_root = MagicMock()
                mock_get_logger.return_value = mock_root

                setup_logging(level="DEBUG", json_format=True)

                mock_json_formatter.assert_called_once()

    def test_setup_logging_with_file(self, tmp_path):
        """Test setup with log file."""
        log_file = tmp_path / "test.log"

        with patch("logging.getLogger") as mock_get_logger:
            with patch("logging.FileHandler") as mock_file_handler:
                mock_root = MagicMock()
                mock_get_logger.return_value = mock_root

                setup_logging(level="INFO", log_file=log_file)

                mock_file_handler.assert_called_once_with(log_file, encoding="utf-8")
                assert mock_root.addHandler.call_count == 2  # Console + File

    def test_setup_logging_creates_directories(self, tmp_path):
        """Test that log file directories are created."""
        log_file = tmp_path / "logs" / "subdir" / "test.log"

        with patch("logging.getLogger"):
            with patch("logging.FileHandler"):
                setup_logging(log_file=log_file)

        assert log_file.parent.exists()

    def test_setup_logging_third_party_levels(self):
        """Test that third-party library levels are reduced."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_root = MagicMock()
            mock_get_logger.return_value = mock_root

            setup_logging(level="DEBUG")

            # Should get logger for third-party libraries
            calls = mock_get_logger.call_args_list
            library_names = [call[0][0] for call in calls]
            assert "urllib3" in library_names or any("urllib3" in str(call) for call in calls)


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger(self):
        """Test getting a logger."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_get_logger.return_value = MagicMock()

            logger = get_logger("test_module")

            mock_get_logger.assert_called_once_with("test_module")
            assert logger is not None


class TestLogWithExtra:
    """Tests for log_with_extra function."""

    def test_log_with_extra(self):
        """Test logging with extra fields."""
        mock_logger = MagicMock()

        log_with_extra(mock_logger, logging.INFO, "Test message", user_id="123", action="login")

        mock_logger.log.assert_called_once()
        call_args = mock_logger.log.call_args

        assert call_args[0][0] == logging.INFO
        assert call_args[0][1] == "Test message"
        assert call_args[1]["extra"]["extra"]["user_id"] == "123"
        assert call_args[1]["extra"]["extra"]["action"] == "login"

    def test_log_with_extra_multiple_fields(self):
        """Test logging with multiple extra fields."""
        mock_logger = MagicMock()

        log_with_extra(
            mock_logger,
            logging.ERROR,
            "Error occurred",
            error_code="E001",
            user_id="123",
            timestamp="2024-01-01",
        )

        call_args = mock_logger.log.call_args
        extra_data = call_args[1]["extra"]["extra"]

        assert extra_data["error_code"] == "E001"
        assert extra_data["user_id"] == "123"
        assert extra_data["timestamp"] == "2024-01-01"


class TestIntegration:
    """Integration tests for logging setup."""

    def test_full_logging_setup(self, tmp_path):
        """Test full logging setup and usage."""
        log_file = tmp_path / "integration.log"

        # Setup logging
        setup_logging(level="DEBUG", json_format=False, log_file=log_file)

        # Get logger and log messages
        logger = get_logger("test.integration")

        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        # Verify log file contains messages
        assert log_file.exists()
        content = log_file.read_text()
        assert "Debug message" in content
        assert "Info message" in content
