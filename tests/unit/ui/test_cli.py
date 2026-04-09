"""Unit tests for CLI interface."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from click.testing import CliRunner

from persona_agent.services import (
    ChatPersonaNotFoundError,
    ChatServiceError,
    ChatSessionNotFoundError,
)
from persona_agent.ui.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestConfigCommand:
    def test_config_list_characters(self, runner):
        with patch("persona_agent.ui.cli.CharacterService") as mock_class:
            instance = mock_class.return_value
            instance.list_characters = Mock(return_value=["default", "companion"])

            result = runner.invoke(cli, ["config", "list"])

            assert result.exit_code == 0
            assert "default" in result.output
            assert "companion" in result.output
            instance.list_characters.assert_called_once()

    def test_config_list_empty(self, runner):
        with patch("persona_agent.ui.cli.CharacterService") as mock_class:
            instance = mock_class.return_value
            instance.list_characters = Mock(return_value=[])

            result = runner.invoke(cli, ["config", "list"])

            assert result.exit_code == 0
            assert "no characters" in result.output.lower()

    def test_config_show_character(self, runner):
        with patch("persona_agent.ui.cli.CharacterService") as mock_class:
            instance = mock_class.return_value
            instance.character_exists = Mock(return_value=True)
            char = Mock()
            char.name = "Test Character"
            char.to_prompt_context = Mock(return_value="Test context")
            instance.get_character = Mock(return_value=char)

            result = runner.invoke(cli, ["config", "show", "default"])

            assert result.exit_code == 0
            assert "Test Character" in result.output
            instance.character_exists.assert_called_once_with("default")
            instance.get_character.assert_called_once_with("default")

    def test_config_show_not_found(self, runner):
        with patch("persona_agent.ui.cli.CharacterService") as mock_class:
            instance = mock_class.return_value
            instance.character_exists = Mock(return_value=False)

            result = runner.invoke(cli, ["config", "show", "nonexistent"])

            assert result.exit_code == 0
            assert "not found" in result.output.lower()

    def test_config_validate(self, runner):
        with patch("persona_agent.config.validator.ConfigValidator") as mock_class:
            mock_validator = Mock()
            mock_validator.validate_all.return_value = True
            mock_class.return_value = mock_validator

            result = runner.invoke(cli, ["config", "validate"])

            assert result.exit_code == 0
            mock_validator.validate_all.assert_called_once()


class TestSessionCommand:
    def test_session_list(self, runner):
        with patch("persona_agent.ui.cli.SessionService") as mock_class:
            instance = mock_class.return_value
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

            result = runner.invoke(cli, ["session", "list"])

            assert result.exit_code == 0
            assert "session-1" in result.output
            instance.list_sessions.assert_called_once_with(limit=20)

    def test_session_list_empty(self, runner):
        with patch("persona_agent.ui.cli.SessionService") as mock_class:
            instance = mock_class.return_value
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=None)
            instance.list_sessions = AsyncMock(return_value=[])

            result = runner.invoke(cli, ["session", "list"])

            assert result.exit_code == 0
            assert "no sessions" in result.output.lower()

    def test_session_info(self, runner):
        with patch("persona_agent.ui.cli.SessionService") as mock_class:
            instance = mock_class.return_value
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=None)
            instance.session_exists = AsyncMock(return_value=True)
            instance.get_session_info = AsyncMock(
                return_value={
                    "session_id": "session-1",
                    "message_count": 5,
                    "first_activity": Mock(strftime=Mock(return_value="2024-01-01 10:00")),
                    "last_activity": Mock(strftime=Mock(return_value="2024-01-01 12:00")),
                    "recent_messages": [],
                }
            )

            result = runner.invoke(cli, ["session", "info", "session-1"])

            assert result.exit_code == 0
            assert "session-1" in result.output
            instance.session_exists.assert_called_once_with("session-1")

    def test_session_info_not_found(self, runner):
        with patch("persona_agent.ui.cli.SessionService") as mock_class:
            instance = mock_class.return_value
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=None)
            instance.session_exists = AsyncMock(return_value=False)

            result = runner.invoke(cli, ["session", "info", "nonexistent"])

            assert result.exit_code == 0
            assert "not found" in result.output.lower()

    def test_session_delete(self, runner):
        with patch("persona_agent.ui.cli.SessionService") as mock_class:
            instance = mock_class.return_value
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=None)
            instance.session_exists = AsyncMock(return_value=True)
            instance.delete_session = AsyncMock(return_value=None)

            result = runner.invoke(cli, ["session", "delete", "session-1", "--yes"])

            assert result.exit_code == 0
            instance.delete_session.assert_called_once_with("session-1")

    def test_session_delete_not_found(self, runner):
        with patch("persona_agent.ui.cli.SessionService") as mock_class:
            instance = mock_class.return_value
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=None)
            instance.session_exists = AsyncMock(return_value=False)

            result = runner.invoke(cli, ["session", "delete", "nonexistent", "--yes"])

            assert result.exit_code == 0
            assert "not found" in result.output.lower()


class TestChatCommandErrorPaths:
    def test_chat_invalid_session_shows_error(self, runner):
        with (
            patch("persona_agent.ui.cli.ChatService") as mock_chat_class,
            patch("persona_agent.ui.cli.CharacterService") as mock_char_class,
        ):
            chat_instance = mock_chat_class.return_value
            chat_instance.__aenter__ = AsyncMock(return_value=chat_instance)
            chat_instance.__aexit__ = AsyncMock(return_value=None)
            chat_instance.get_session_info = AsyncMock(
                side_effect=ChatSessionNotFoundError("invalid-session")
            )

            char_instance = mock_char_class.return_value
            char_instance.list_characters = Mock(return_value=["default"])

            result = runner.invoke(cli, ["chat", "--session", "invalid-session"])

            assert result.exit_code == 0
            assert "not found" in result.output.lower()

    def test_chat_invalid_persona_shows_error(self, runner):
        with (
            patch("persona_agent.ui.cli.ChatService") as mock_chat_class,
            patch("persona_agent.ui.cli.CharacterService") as mock_char_class,
        ):
            chat_instance = mock_chat_class.return_value
            chat_instance.__aenter__ = AsyncMock(return_value=chat_instance)
            chat_instance.__aexit__ = AsyncMock(return_value=None)
            chat_instance.create_new_session = AsyncMock(
                side_effect=ChatPersonaNotFoundError("invalid-persona")
            )

            char_instance = mock_char_class.return_value
            char_instance.list_characters = Mock(return_value=["default"])

            result = runner.invoke(cli, ["chat", "--persona", "invalid-persona"])

            assert result.exit_code == 0
            assert "not found" in result.output.lower()

    def test_chat_service_error_handling(self, runner):
        with (
            patch("persona_agent.ui.cli.ChatService") as mock_chat_class,
            patch("persona_agent.ui.cli.CharacterService") as mock_char_class,
        ):
            chat_instance = mock_chat_class.return_value
            chat_instance.__aenter__ = AsyncMock(return_value=chat_instance)
            chat_instance.__aexit__ = AsyncMock(return_value=None)
            chat_instance.create_new_session = AsyncMock(
                side_effect=ChatServiceError("Connection failed")
            )

            char_instance = mock_char_class.return_value
            char_instance.list_characters = Mock(return_value=["default"])

            result = runner.invoke(cli, ["chat"])

            assert result.exit_code == 0
            assert "Error" in result.output or "Failed" in result.output


class TestChatCommandSuccessPaths:
    def test_chat_with_default_persona(self, runner):
        with (
            patch("persona_agent.ui.cli.ChatService") as mock_chat_class,
            patch("persona_agent.ui.cli.CharacterService") as mock_char_class,
            patch("persona_agent.ui.cli.console") as mock_console,
        ):
            chat_instance = mock_chat_class.return_value
            chat_instance.__aenter__ = AsyncMock(return_value=chat_instance)
            chat_instance.__aexit__ = AsyncMock(return_value=None)
            chat_instance.create_new_session = AsyncMock(return_value="test-session-123")

            char_instance = mock_char_class.return_value
            char_instance.list_characters = Mock(return_value=["default"])
            char_mock = Mock()
            char_mock.name = "Test Character"
            char_mock.relationship = "Friend"
            char_instance.get_character = Mock(return_value=char_mock)

            mock_console.input = Mock(return_value="exit")

            result = runner.invoke(cli, ["chat"])

            assert result.exit_code == 0
            chat_instance.create_new_session.assert_called_once()

    def test_chat_with_specific_persona(self, runner):
        with (
            patch("persona_agent.ui.cli.ChatService") as mock_chat_class,
            patch("persona_agent.ui.cli.CharacterService") as mock_char_class,
            patch("persona_agent.ui.cli.console") as mock_console,
        ):
            chat_instance = mock_chat_class.return_value
            chat_instance.__aenter__ = AsyncMock(return_value=chat_instance)
            chat_instance.__aexit__ = AsyncMock(return_value=None)
            chat_instance.create_new_session = AsyncMock(return_value="test-session-123")

            char_instance = mock_char_class.return_value
            char_mock = Mock()
            char_mock.name = "Companion"
            char_mock.relationship = "Friend"
            char_instance.get_character = Mock(return_value=char_mock)

            mock_console.input = Mock(return_value="exit")

            result = runner.invoke(cli, ["chat", "--persona", "companion"])

            assert result.exit_code == 0
            chat_instance.create_new_session.assert_called_once_with(persona_name="companion")

    def test_chat_resume_session(self, runner):
        with (
            patch("persona_agent.ui.cli.ChatService") as mock_chat_class,
            patch("persona_agent.ui.cli.CharacterService") as mock_char_class,
            patch("persona_agent.ui.cli.console") as mock_console,
        ):
            chat_instance = mock_chat_class.return_value
            chat_instance.__aenter__ = AsyncMock(return_value=chat_instance)
            chat_instance.__aexit__ = AsyncMock(return_value=None)
            chat_instance.get_session_info = AsyncMock(
                return_value={
                    "session_id": "existing-session",
                    "persona_name": "companion",
                    "message_count": 5,
                }
            )

            char_instance = mock_char_class.return_value
            char_mock = Mock()
            char_mock.name = "Companion"
            char_mock.relationship = "Friend"
            char_instance.get_character = Mock(return_value=char_mock)

            mock_console.input = Mock(return_value="exit")

            result = runner.invoke(cli, ["chat", "--session", "existing-session"])

            assert result.exit_code == 0
            chat_instance.get_session_info.assert_called_once_with("existing-session")
            chat_instance.create_new_session.assert_not_called()

    def test_chat_keyboard_interrupt(self, runner):
        with (
            patch("persona_agent.ui.cli.ChatService") as mock_chat_class,
            patch("persona_agent.ui.cli.CharacterService") as mock_char_class,
            patch("persona_agent.ui.cli.console") as mock_console,
        ):
            chat_instance = mock_chat_class.return_value
            chat_instance.__aenter__ = AsyncMock(return_value=chat_instance)
            chat_instance.__aexit__ = AsyncMock(return_value=None)
            chat_instance.create_new_session = AsyncMock(return_value="test-session-123")

            char_instance = mock_char_class.return_value
            char_instance.list_characters = Mock(return_value=["default"])
            char_mock = Mock()
            char_mock.name = "Test Character"
            char_mock.relationship = "Friend"
            char_instance.get_character = Mock(return_value=char_mock)

            mock_console.input = Mock(side_effect=KeyboardInterrupt)

            result = runner.invoke(cli, ["chat"])

            assert result.exit_code == 0
