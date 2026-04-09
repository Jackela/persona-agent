"""Comprehensive unit tests for CLI commands using Click CliRunner.

This module provides comprehensive tests for the CLI interface,
mocking all service layer dependencies to test command behavior
and error handling in isolation.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from click.testing import CliRunner

from persona_agent.ui.cli import cli
from persona_agent.config.schemas.character import CharacterProfile
from persona_agent.services import (
    ChatService,
    CharacterService,
    SessionService,
    ChatSessionNotFoundError,
    ChatPersonaNotFoundError,
    ChatServiceError,
    CharacterNotFoundError,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def runner():
    """Create a Click CliRunner."""
    return CliRunner()


@pytest.fixture
def mock_character_profile():
    """Create a mock character profile."""
    profile = Mock(spec=CharacterProfile)
    profile.name = "Test Character"
    profile.relationship = "Your companion"
    profile.to_prompt_context.return_value = "You are Test Character."
    return profile


@pytest.fixture
def mock_chat_service():
    """Mock ChatService for testing."""
    with patch("persona_agent.ui.cli.ChatService") as mock:
        instance = mock.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)

        # Default successful responses
        instance.create_new_session = AsyncMock(return_value="test-session-123")
        instance.get_session_info = AsyncMock(
            return_value={
                "session_id": "test-session-123",
                "persona_name": "default",
                "message_count": 0,
            }
        )
        instance.send_message = AsyncMock(return_value="Hello! I'm your assistant.")
        instance.get_conversation_history = AsyncMock(return_value=[])
        instance.switch_persona = AsyncMock(return_value=None)
        instance.close = AsyncMock(return_value=None)
        yield instance


@pytest.fixture
def mock_character_service():
    """Mock CharacterService for testing."""
    with patch("persona_agent.ui.cli.CharacterService") as mock:
        instance = mock.return_value
        instance.list_characters = Mock(return_value=["default", "companion"])

        char = Mock()
        char.name = "Test Character"
        char.relationship = "Your friend"
        char.to_prompt_context = Mock(return_value="Test character context")
        instance.get_character = Mock(return_value=char)
        instance.character_exists = Mock(return_value=True)
        yield instance


@pytest.fixture
def mock_session_service():
    """Mock SessionService for testing."""
    with patch("persona_agent.ui.cli.SessionService") as mock:
        instance = mock.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)

        instance.list_sessions = AsyncMock(
            return_value=[
                {
                    "session_id": "session-1",
                    "message_count": 5,
                    "last_activity": Mock(strftime=Mock(return_value="2024-01-01 12:00")),
                }
            ]
        )
        instance.get_session_info = AsyncMock(
            return_value={
                "session_id": "session-1",
                "message_count": 5,
                "first_activity": Mock(strftime=Mock(return_value="2024-01-01 10:00")),
                "last_activity": Mock(strftime=Mock(return_value="2024-01-01 12:00")),
                "recent_messages": [],
            }
        )
        instance.session_exists = AsyncMock(return_value=True)
        instance.delete_session = AsyncMock(return_value=None)
        yield instance


# ============================================================================
# Chat Command Tests
# ============================================================================


class TestChatCommand:
    """Tests for the chat command."""

    def test_chat_with_default_persona(self, runner, mock_chat_service, mock_character_service):
        """Test chat command with default persona (no --persona option)."""
        # Simulate user typing 'exit' immediately
        with runner.isolation(input="exit\n"):
            result = runner.invoke(cli, ["chat"])

        assert result.exit_code == 0
        mock_chat_service.create_new_session.assert_called_once()
        mock_character_service.list_characters.assert_called_once()

    def test_chat_with_specific_persona(self, runner, mock_chat_service, mock_character_service):
        """Test chat command with specific persona using --persona option."""
        with runner.isolation(input="exit\n"):
            result = runner.invoke(cli, ["chat", "--persona", "companion"])

        assert result.exit_code == 0
        mock_chat_service.create_new_session.assert_called_once_with(persona_name="companion")

    def test_chat_resume_session(self, runner, mock_chat_service, mock_character_service):
        """Test chat command resuming existing session using --session option."""
        with runner.isolation(input="exit\n"):
            result = runner.invoke(cli, ["chat", "--session", "existing-session"])

        assert result.exit_code == 0
        mock_chat_service.get_session_info.assert_called_once_with("existing-session")
        mock_chat_service.create_new_session.assert_not_called()

    def test_chat_invalid_session_shows_error(self, runner, mock_chat_service):
        """Test chat command with invalid session shows appropriate error message."""
        mock_chat_service.get_session_info.side_effect = ChatSessionNotFoundError("invalid-session")

        result = runner.invoke(cli, ["chat", "--session", "invalid-session"])

        assert result.exit_code == 0
        assert "not found" in result.output.lower()

    def test_chat_invalid_persona_shows_error(self, runner, mock_chat_service):
        """Test chat command with invalid persona shows appropriate error message."""
        mock_chat_service.create_new_session.side_effect = ChatPersonaNotFoundError(
            "invalid-persona"
        )

        result = runner.invoke(cli, ["chat", "--persona", "invalid-persona"])

        assert result.exit_code == 0
        assert "not found" in result.output.lower()

    def test_chat_keyboard_interrupt(self, runner, mock_chat_service, mock_character_service):
        """Test chat command handles keyboard interrupt gracefully."""
        with runner.isolation(input=""):
            result = runner.invoke(cli, ["chat"])

        # Should exit cleanly
        assert result.exit_code == 0

    def test_chat_service_error_handling(self, runner, mock_chat_service):
        """Test chat command handles service errors gracefully."""
        mock_chat_service.create_new_session.side_effect = ChatServiceError("Connection failed")

        result = runner.invoke(cli, ["chat"])

        assert result.exit_code == 0
        assert "Error" in result.output or "Failed" in result.output


# ============================================================================
# Config Command Tests
# ============================================================================


class TestConfigCommand:
    """Tests for the config command group."""

    def test_config_list_characters(self, runner, mock_character_service):
        """Test config list command shows available characters."""
        result = runner.invoke(cli, ["config", "list"])

        assert result.exit_code == 0
        assert "default" in result.output
        assert "companion" in result.output
        mock_character_service.list_characters.assert_called_once()

    def test_config_list_empty(self, runner, mock_character_service):
        """Test config list command when no characters exist."""
        mock_character_service.list_characters.return_value = []

        result = runner.invoke(cli, ["config", "list"])

        assert result.exit_code == 0
        assert "no characters" in result.output.lower()

    def test_config_show_character(self, runner, mock_character_service):
        """Test config show command displays character details."""
        result = runner.invoke(cli, ["config", "show", "default"])

        assert result.exit_code == 0
        assert "Test Character" in result.output
        mock_character_service.character_exists.assert_called_once_with("default")
        mock_character_service.get_character.assert_called_once_with("default")

    def test_config_show_not_found(self, runner, mock_character_service):
        """Test config show command with non-existent character."""
        mock_character_service.character_exists.return_value = False

        result = runner.invoke(cli, ["config", "show", "nonexistent"])

        assert result.exit_code == 0
        assert "not found" in result.output.lower()

    def test_config_validate(self, runner):
        """Test config validate command validates configuration files."""
        with patch("persona_agent.ui.cli.ConfigValidator") as mock_class:
            mock_validator = Mock()
            mock_validator.validate_all.return_value = True
            mock_class.return_value = mock_validator

            result = runner.invoke(cli, ["config", "validate"])

            assert result.exit_code == 0
            mock_validator.validate_all.assert_called_once()


# ============================================================================
# Session Command Tests
# ============================================================================


class TestSessionCommand:
    """Tests for the session command group."""

    def test_session_list(self, runner, mock_session_service):
        """Test session list command displays sessions."""
        result = runner.invoke(cli, ["session", "list"])

        assert result.exit_code == 0
        assert "session-1" in result.output
        mock_session_service.list_sessions.assert_called_once_with(limit=20)

    def test_session_list_empty(self, runner, mock_session_service):
        """Test session list command when no sessions exist."""
        mock_session_service.list_sessions.return_value = []

        result = runner.invoke(cli, ["session", "list"])

        assert result.exit_code == 0
        assert "no sessions" in result.output.lower()

    def test_session_info(self, runner, mock_session_service):
        """Test session info command displays session details."""
        result = runner.invoke(cli, ["session", "info", "session-1"])

        assert result.exit_code == 0
        assert "session-1" in result.output
        mock_session_service.session_exists.assert_called_once_with("session-1")

    def test_session_info_not_found(self, runner, mock_session_service):
        """Test session info command with non-existent session."""
        mock_session_service.session_exists.return_value = False

        result = runner.invoke(cli, ["session", "info", "nonexistent"])

        assert result.exit_code == 0
        assert "not found" in result.output.lower()

    def test_session_delete(self, runner, mock_session_service):
        """Test session delete command deletes session."""
        # Use --yes flag to skip confirmation
        result = runner.invoke(cli, ["session", "delete", "session-1", "--yes"])

        assert result.exit_code == 0
        mock_session_service.delete_session.assert_called_once_with("session-1")

    def test_session_delete_not_found(self, runner, mock_session_service):
        """Test session delete command with non-existent session."""
        mock_session_service.session_exists.return_value = False

        result = runner.invoke(cli, ["session", "delete", "nonexistent", "--yes"])

        assert result.exit_code == 0
        assert "not found" in result.output.lower()
