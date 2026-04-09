"""Unit tests for ChatService."""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from persona_agent.services.chat_service import (
    ChatService,
    ChatSessionNotFoundError,
    ChatPersonaNotFoundError,
    ChatLLMError,
    ChatMessageError,
)
from persona_agent.services.character_service import CharacterNotFoundError
from persona_agent.repositories import Session


class TestChatService:
    """Test suite for ChatService."""

    @pytest.fixture
    def mock_character_service(self):
        """Create a mock CharacterService."""
        mock = Mock()
        mock.character_exists.return_value = True
        return mock

    @pytest.fixture
    def mock_session_service(self):
        """Create a mock SessionService."""
        mock = AsyncMock()
        return mock

    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLMClient."""
        mock = AsyncMock()
        return mock

    @pytest.fixture
    def mock_session_repo(self):
        """Create a mock SessionRepository."""
        mock = AsyncMock()
        mock.is_connected.return_value = True
        return mock

    @pytest.fixture
    def chat_service(
        self,
        mock_character_service,
        mock_session_service,
        mock_llm_client,
        mock_session_repo,
    ):
        """Create a ChatService instance with mocked dependencies."""
        service = ChatService(
            character_service=mock_character_service,
            session_service=mock_session_service,
            llm_client=mock_llm_client,
            db_path=":memory:",
        )
        service._session_repo = mock_session_repo
        return service

    @pytest.fixture
    def mock_character_profile(self):
        """Create a mock CharacterProfile."""
        mock = Mock()
        mock.name = "Test Character"
        mock.to_prompt_context.return_value = "You are Test Character."
        return mock

    @pytest.fixture
    def mock_session(self):
        """Create a mock Session with messages."""
        return Session(
            session_id="test-session-123",
            messages=[
                {
                    "role": "system",
                    "content": "persona:default",
                    "timestamp": datetime.now().timestamp(),
                },
                {
                    "role": "user",
                    "content": "Hello",
                    "timestamp": datetime.now().timestamp(),
                },
            ],
            last_activity=datetime.now(),
        )

    # ==========================================================================
    # create_new_session tests
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_create_new_session_with_default_persona(
        self, chat_service, mock_character_service, mock_session_repo
    ):
        """Test creating a new session with default persona."""
        # Arrange
        mock_character_service.character_exists.return_value = True

        # Act
        session_id = await chat_service.create_new_session()

        # Assert
        assert session_id is not None
        assert isinstance(session_id, str)
        mock_character_service.character_exists.assert_called_once_with("default")
        mock_session_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_new_session_with_custom_persona(
        self, chat_service, mock_character_service, mock_session_repo
    ):
        """Test creating a new session with a specific persona."""
        # Arrange
        mock_character_service.character_exists.return_value = True

        # Act
        session_id = await chat_service.create_new_session(persona_name="companion")

        # Assert
        assert session_id is not None
        mock_character_service.character_exists.assert_called_once_with("companion")
        created_session = mock_session_repo.create.call_args[0][0]
        assert created_session.messages[0]["content"] == "persona:companion"

    @pytest.mark.asyncio
    async def test_create_new_session_with_custom_id(
        self, chat_service, mock_character_service, mock_session_repo
    ):
        """Test creating a new session with a custom session ID."""
        # Arrange
        mock_character_service.character_exists.return_value = True
        custom_id = "my-custom-session-id"

        # Act
        session_id = await chat_service.create_new_session(session_id=custom_id)

        # Assert
        assert session_id == custom_id
        created_session = mock_session_repo.create.call_args[0][0]
        assert created_session.session_id == custom_id

    @pytest.mark.asyncio
    async def test_create_new_session_persona_not_found(self, chat_service, mock_character_service):
        """Test creating a session with non-existent persona raises error."""
        # Arrange
        mock_character_service.character_exists.return_value = False

        # Act & Assert
        with pytest.raises(ChatPersonaNotFoundError) as exc_info:
            await chat_service.create_new_session(persona_name="nonexistent")

        assert "nonexistent" in str(exc_info.value)
        assert exc_info.value.code == "CHAT_PERSONA_NOT_FOUND"
        assert exc_info.value.details["persona_name"] == "nonexistent"

    @pytest.mark.asyncio
    async def test_create_new_session_ensures_connection(
        self, chat_service, mock_character_service, mock_session_repo
    ):
        """Test that create_new_session ensures repository is connected."""
        # Arrange
        mock_character_service.character_exists.return_value = True
        mock_session_repo.is_connected.return_value = False

        # Act
        await chat_service.create_new_session()

        # Assert
        mock_session_repo.connect.assert_called_once()

    # ==========================================================================
    # send_message tests
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_send_message_success(
        self,
        chat_service,
        mock_session_repo,
        mock_character_service,
        mock_llm_client,
        mock_character_profile,
        mock_session,
    ):
        """Test sending a message successfully."""
        # Arrange
        mock_session_repo.get_by_id.return_value = mock_session
        mock_character_service.get_character.return_value = mock_character_profile
        mock_llm_response = Mock()
        mock_llm_response.content = "Hello! How can I help you?"
        mock_llm_client.chat.return_value = mock_llm_response

        # Act
        response = await chat_service.send_message("test-session-123", "How are you?")

        # Assert
        assert response == "Hello! How can I help you?"
        mock_session_repo.get_by_id.assert_called_once_with("test-session-123")
        mock_character_service.get_character.assert_called_once_with("default")
        mock_llm_client.chat.assert_called_once()
        mock_session_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_empty_message_raises_error(self, chat_service):
        """Test sending an empty message raises ChatMessageError."""
        # Act & Assert
        with pytest.raises(ChatMessageError) as exc_info:
            await chat_service.send_message("test-session-123", "")

        assert "cannot be empty" in str(exc_info.value)
        assert exc_info.value.code == "CHAT_MESSAGE_ERROR"

    @pytest.mark.asyncio
    async def test_send_message_whitespace_only_raises_error(self, chat_service):
        """Test sending whitespace-only message raises ChatMessageError."""
        # Act & Assert
        with pytest.raises(ChatMessageError) as exc_info:
            await chat_service.send_message("test-session-123", "   ")

        assert "cannot be empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_send_message_session_not_found(self, chat_service, mock_session_repo):
        """Test sending a message to non-existent session raises error."""
        # Arrange
        mock_session_repo.get_by_id.return_value = None

        # Act & Assert
        with pytest.raises(ChatSessionNotFoundError) as exc_info:
            await chat_service.send_message("nonexistent", "Hello")

        assert "nonexistent" in str(exc_info.value)
        assert exc_info.value.code == "CHAT_SESSION_NOT_FOUND"
        assert exc_info.value.details["session_id"] == "nonexistent"

    @pytest.mark.asyncio
    async def test_send_message_persona_not_found(
        self, chat_service, mock_session_repo, mock_character_service, mock_session
    ):
        """Test sending a message when persona doesn't exist raises error."""
        # Arrange
        mock_session_repo.get_by_id.return_value = mock_session
        mock_character_service.get_character.side_effect = CharacterNotFoundError("default")

        # Act & Assert
        with pytest.raises(ChatPersonaNotFoundError) as exc_info:
            await chat_service.send_message("test-session-123", "Hello")

        assert "default" in str(exc_info.value)
        assert exc_info.value.code == "CHAT_PERSONA_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_send_message_llm_error(
        self,
        chat_service,
        mock_session_repo,
        mock_character_service,
        mock_llm_client,
        mock_character_profile,
        mock_session,
    ):
        """Test LLM error during send_message raises ChatLLMError."""
        # Arrange
        mock_session_repo.get_by_id.return_value = mock_session
        mock_character_service.get_character.return_value = mock_character_profile
        mock_llm_client.chat.side_effect = Exception("LLM API Error")

        # Act & Assert
        with pytest.raises(ChatLLMError) as exc_info:
            await chat_service.send_message("test-session-123", "Hello")

        assert "Failed to get LLM response" in str(exc_info.value)
        assert exc_info.value.code == "CHAT_LLM_ERROR"
        assert exc_info.value.details["session_id"] == "test-session-123"

    @pytest.mark.asyncio
    async def test_send_message_with_temperature_and_max_tokens(
        self,
        chat_service,
        mock_session_repo,
        mock_character_service,
        mock_llm_client,
        mock_character_profile,
        mock_session,
    ):
        """Test sending a message with custom temperature and max_tokens."""
        # Arrange
        mock_session_repo.get_by_id.return_value = mock_session
        mock_character_service.get_character.return_value = mock_character_profile
        mock_llm_response = Mock()
        mock_llm_response.content = "Response"
        mock_llm_client.chat.return_value = mock_llm_response

        # Act
        await chat_service.send_message(
            "test-session-123", "Hello", temperature=0.5, max_tokens=100
        )

        # Assert
        mock_llm_client.chat.assert_called_once_with(
            messages=mock_llm_client.chat.call_args[1]["messages"],
            temperature=0.5,
            max_tokens=100,
        )

    @pytest.mark.asyncio
    async def test_send_message_updates_session_messages(
        self,
        chat_service,
        mock_session_repo,
        mock_character_service,
        mock_llm_client,
        mock_character_profile,
        mock_session,
    ):
        """Test that send_message adds user and assistant messages to session."""
        # Arrange
        mock_session_repo.get_by_id.return_value = mock_session
        mock_character_service.get_character.return_value = mock_character_profile
        mock_llm_response = Mock()
        mock_llm_response.content = "AI Response"
        mock_llm_client.chat.return_value = mock_llm_response
        original_message_count = len(mock_session.messages)

        # Act
        await chat_service.send_message("test-session-123", "User message")

        # Assert
        assert len(mock_session.messages) == original_message_count + 2
        assert mock_session.messages[-2]["role"] == "user"
        assert mock_session.messages[-2]["content"] == "User message"
        assert mock_session.messages[-1]["role"] == "assistant"
        assert mock_session.messages[-1]["content"] == "AI Response"
        mock_session_repo.update.assert_called_once_with(mock_session)

    @pytest.mark.asyncio
    async def test_send_message_updates_last_activity(
        self,
        chat_service,
        mock_session_repo,
        mock_character_service,
        mock_llm_client,
        mock_character_profile,
        mock_session,
    ):
        """Test that send_message updates session last_activity."""
        # Arrange
        mock_session_repo.get_by_id.return_value = mock_session
        mock_character_service.get_character.return_value = mock_character_profile
        mock_llm_response = Mock()
        mock_llm_response.content = "Response"
        mock_llm_client.chat.return_value = mock_llm_response
        original_last_activity = mock_session.last_activity

        # Act
        await chat_service.send_message("test-session-123", "Hello")

        # Assert
        assert mock_session.last_activity > original_last_activity

    @pytest.mark.asyncio
    async def test_send_message_extracts_persona_from_session(
        self,
        chat_service,
        mock_session_repo,
        mock_character_service,
        mock_llm_client,
        mock_character_profile,
    ):
        """Test that persona is extracted from session's first system message."""
        # Arrange
        session = Session(
            session_id="test-session-123",
            messages=[
                {
                    "role": "system",
                    "content": "persona:companion",
                    "timestamp": datetime.now().timestamp(),
                }
            ],
            last_activity=datetime.now(),
        )
        mock_session_repo.get_by_id.return_value = session
        mock_character_service.get_character.return_value = mock_character_profile
        mock_llm_response = Mock()
        mock_llm_response.content = "Response"
        mock_llm_client.chat.return_value = mock_llm_response

        # Act
        await chat_service.send_message("test-session-123", "Hello")

        # Assert
        mock_character_service.get_character.assert_called_once_with("companion")

    # ==========================================================================
    # get_conversation_history tests
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_get_conversation_history_success(
        self, chat_service, mock_session_repo, mock_session
    ):
        """Test getting conversation history."""
        # Arrange
        mock_session_repo.get_by_id.return_value = mock_session

        # Act
        history = await chat_service.get_conversation_history("test-session-123")

        # Assert
        assert len(history) == 1  # One user message (system excluded by default)
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_get_conversation_history_include_system(
        self, chat_service, mock_session_repo, mock_session
    ):
        """Test getting conversation history including system messages."""
        # Arrange
        mock_session_repo.get_by_id.return_value = mock_session

        # Act
        history = await chat_service.get_conversation_history(
            "test-session-123", include_system=True
        )

        # Assert
        assert len(history) == 2  # Both system and user messages

    @pytest.mark.asyncio
    async def test_get_conversation_history_session_not_found(
        self, chat_service, mock_session_repo
    ):
        """Test getting history for non-existent session raises error."""
        # Arrange
        mock_session_repo.get_by_id.return_value = None

        # Act & Assert
        with pytest.raises(ChatSessionNotFoundError) as exc_info:
            await chat_service.get_conversation_history("nonexistent")

        assert "nonexistent" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_conversation_history_empty_session(self, chat_service, mock_session_repo):
        """Test getting history from empty session."""
        # Arrange
        empty_session = Session(
            session_id="empty-session",
            messages=[],
            last_activity=datetime.now(),
        )
        mock_session_repo.get_by_id.return_value = empty_session

        # Act
        history = await chat_service.get_conversation_history("empty-session")

        # Assert
        assert history == []

    # ==========================================================================
    # switch_persona tests
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_switch_persona_success(
        self,
        chat_service,
        mock_character_service,
        mock_session_repo,
        mock_character_profile,
        mock_session,
    ):
        """Test switching persona successfully."""
        # Arrange
        mock_character_service.character_exists.return_value = True
        mock_character_service.get_character.return_value = mock_character_profile
        mock_session_repo.get_by_id.return_value = mock_session

        # Act
        result = await chat_service.switch_persona("test-session-123", "companion")

        # Assert
        assert "switched to 'companion'" in result
        assert mock_session.messages[0]["content"] == "persona:companion"
        mock_session_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_switch_persona_not_found(self, chat_service, mock_character_service):
        """Test switching to non-existent persona raises error."""
        # Arrange
        mock_character_service.character_exists.return_value = False

        # Act & Assert
        with pytest.raises(ChatPersonaNotFoundError) as exc_info:
            await chat_service.switch_persona("test-session-123", "nonexistent")

        assert "nonexistent" in str(exc_info.value)
        mock_character_service.character_exists.assert_called_once_with("nonexistent")

    @pytest.mark.asyncio
    async def test_switch_persona_session_not_found(
        self, chat_service, mock_character_service, mock_session_repo
    ):
        """Test switching persona for non-existent session raises error."""
        # Arrange
        mock_character_service.character_exists.return_value = True
        mock_session_repo.get_by_id.return_value = None

        # Act & Assert
        with pytest.raises(ChatSessionNotFoundError) as exc_info:
            await chat_service.switch_persona("nonexistent", "companion")

        assert "nonexistent" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_switch_persona_without_transition_message(
        self,
        chat_service,
        mock_character_service,
        mock_session_repo,
        mock_character_profile,
        mock_session,
    ):
        """Test switching persona without adding transition message."""
        # Arrange
        mock_character_service.character_exists.return_value = True
        mock_character_service.get_character.return_value = mock_character_profile
        mock_session_repo.get_by_id.return_value = mock_session
        original_message_count = len(mock_session.messages)

        # Act
        await chat_service.switch_persona(
            "test-session-123", "companion", add_transition_message=False
        )

        # Assert
        assert len(mock_session.messages) == original_message_count
        assert mock_session.messages[0]["content"] == "persona:companion"

    @pytest.mark.asyncio
    async def test_switch_persona_adds_transition_message(
        self,
        chat_service,
        mock_character_service,
        mock_session_repo,
        mock_character_profile,
        mock_session,
    ):
        """Test switching persona adds transition message."""
        # Arrange
        mock_character_service.character_exists.return_value = True
        mock_character_service.get_character.return_value = mock_character_profile
        mock_session_repo.get_by_id.return_value = mock_session
        original_message_count = len(mock_session.messages)

        # Act
        await chat_service.switch_persona(
            "test-session-123", "companion", add_transition_message=True
        )

        # Assert
        assert len(mock_session.messages) == original_message_count + 1
        assert "Persona switched to" in mock_session.messages[-1]["content"]
        assert mock_session.messages[-1]["role"] == "system"

    @pytest.mark.asyncio
    async def test_switch_persona_inserts_at_beginning_if_no_system(
        self,
        chat_service,
        mock_character_service,
        mock_session_repo,
        mock_character_profile,
    ):
        """Test switching persona inserts marker at beginning if no system message."""
        # Arrange
        mock_character_service.character_exists.return_value = True
        mock_character_service.get_character.return_value = mock_character_profile
        session_without_system = Session(
            session_id="test-session-123",
            messages=[{"role": "user", "content": "Hello"}],
            last_activity=datetime.now(),
        )
        mock_session_repo.get_by_id.return_value = session_without_system

        # Act
        await chat_service.switch_persona("test-session-123", "companion")

        # Assert
        assert session_without_system.messages[0]["role"] == "system"
        assert session_without_system.messages[0]["content"] == "persona:companion"

    # ==========================================================================
    # get_session_info tests
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_get_session_info_success(self, chat_service, mock_session_repo, mock_session):
        """Test getting session information."""
        # Arrange
        mock_session_repo.get_by_id.return_value = mock_session

        # Act
        info = await chat_service.get_session_info("test-session-123")

        # Assert
        assert info["session_id"] == "test-session-123"
        assert info["persona_name"] == "default"
        assert info["message_count"] == 1  # Only user message (excluding system)
        assert isinstance(info["first_activity"], datetime)
        assert isinstance(info["last_activity"], datetime)

    @pytest.mark.asyncio
    async def test_get_session_info_session_not_found(self, chat_service, mock_session_repo):
        """Test getting info for non-existent session raises error."""
        # Arrange
        mock_session_repo.get_by_id.return_value = None

        # Act & Assert
        with pytest.raises(ChatSessionNotFoundError) as exc_info:
            await chat_service.get_session_info("nonexistent")

        assert "nonexistent" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_session_info_empty_session(self, chat_service, mock_session_repo):
        """Test getting info for empty session."""
        # Arrange
        empty_session = Session(
            session_id="empty-session",
            messages=[],
            last_activity=datetime.now(),
        )
        mock_session_repo.get_by_id.return_value = empty_session

        # Act
        info = await chat_service.get_session_info("empty-session")

        # Assert
        assert info["session_id"] == "empty-session"
        assert info["persona_name"] == "default"  # Falls back to default
        assert info["message_count"] == 0

    @pytest.mark.asyncio
    async def test_get_session_info_uses_first_message_timestamp(
        self, chat_service, mock_session_repo
    ):
        """Test that first_activity uses first message timestamp."""
        # Arrange
        first_timestamp = datetime(2024, 1, 1, 10, 0).timestamp()
        session = Session(
            session_id="test-session",
            messages=[
                {
                    "role": "system",
                    "content": "persona:default",
                    "timestamp": first_timestamp,
                }
            ],
            last_activity=datetime(2024, 1, 2, 10, 0),
        )
        mock_session_repo.get_by_id.return_value = session

        # Act
        info = await chat_service.get_session_info("test-session")

        # Assert
        assert info["first_activity"] == datetime.fromtimestamp(first_timestamp)

    # ==========================================================================
    # _ensure_connected tests
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_ensure_connected_when_not_connected(self, chat_service, mock_session_repo):
        """Test ensuring connection when not connected."""
        # Arrange
        mock_session_repo.is_connected.return_value = False

        # Act
        await chat_service._ensure_connected()

        # Assert
        mock_session_repo.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_connected_when_already_connected(self, chat_service, mock_session_repo):
        """Test ensuring connection when already connected."""
        # Arrange
        mock_session_repo.is_connected.return_value = True

        # Act
        await chat_service._ensure_connected()

        # Assert
        mock_session_repo.connect.assert_not_called()

    # ==========================================================================
    # _build_messages_for_llm tests
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_build_messages_for_llm(self, chat_service, mock_session, mock_character_profile):
        """Test building messages for LLM."""
        # Act
        messages = await chat_service._build_messages_for_llm(
            mock_session, mock_character_profile, "New message"
        )

        # Assert
        assert len(messages) == 4  # system + 2 existing + new user message
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are Test Character."
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "New message"

    @pytest.mark.asyncio
    async def test_build_messages_for_llm_without_new_message(
        self, chat_service, mock_session, mock_character_profile
    ):
        """Test building messages without new user message."""
        # Act
        messages = await chat_service._build_messages_for_llm(mock_session, mock_character_profile)

        # Assert
        assert len(messages) == 3  # system + 2 existing
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "Hello"

    # ==========================================================================
    # close tests
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_close(self, chat_service, mock_session_repo, mock_session_service):
        """Test closing the service."""
        # Act
        await chat_service.close()

        # Assert
        mock_session_repo.disconnect.assert_called_once()
        mock_session_service.close.assert_called_once()

    # ==========================================================================
    # async context manager tests
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_async_context_manager(self, chat_service, mock_session_repo):
        """Test using service as async context manager."""
        # Arrange
        mock_session_repo.is_connected.return_value = False

        # Act
        async with chat_service as svc:
            assert svc == chat_service

        # Assert
        mock_session_repo.connect.assert_called_once()
        mock_session_repo.disconnect.assert_called_once()

    # ==========================================================================
    # Initialization tests
    # ==========================================================================

    def test_init_with_default_dependencies(self):
        """Test initialization with default dependencies."""
        with (
            patch("persona_agent.services.chat_service.CharacterService") as mock_char_service,
            patch("persona_agent.services.chat_service.SessionService") as mock_sess_service,
            patch("persona_agent.services.chat_service.SessionRepository") as mock_repo,
            patch("persona_agent.services.chat_service.LLMClient") as mock_llm,
        ):
            service = ChatService()

            mock_char_service.assert_called_once()
            mock_repo.assert_called_once_with("memory/persona_agent.db")
            mock_sess_service.assert_called_once_with(
                "memory/persona_agent.db", session_repo=mock_repo.return_value
            )
            mock_llm.assert_called_once_with(provider="openai", model=None)

    def test_init_with_custom_llm_settings(self):
        """Test initialization with custom LLM provider and model."""
        with (
            patch("persona_agent.services.chat_service.CharacterService") as mock_char_service,
            patch("persona_agent.services.chat_service.SessionService") as mock_sess_service,
            patch("persona_agent.services.chat_service.SessionRepository") as mock_repo,
            patch("persona_agent.services.chat_service.LLMClient") as mock_llm,
        ):
            service = ChatService(
                llm_provider="anthropic",
                llm_model="claude-3-opus",
                default_persona="companion",
            )

            assert service._default_persona == "companion"
            mock_llm.assert_called_once_with(provider="anthropic", model="claude-3-opus")

    # ==========================================================================
    # Error handling tests
    # ==========================================================================

    def test_chat_session_not_found_error(self):
        """Test ChatSessionNotFoundError includes proper details."""
        # Arrange & Act
        error = ChatSessionNotFoundError("test-session")

        # Assert
        assert "test-session" in str(error)
        assert error.code == "CHAT_SESSION_NOT_FOUND"
        assert error.details["session_id"] == "test-session"

    def test_chat_persona_not_found_error(self):
        """Test ChatPersonaNotFoundError includes proper details."""
        # Arrange & Act
        error = ChatPersonaNotFoundError("unknown-persona")

        # Assert
        assert "unknown-persona" in str(error)
        assert error.code == "CHAT_PERSONA_NOT_FOUND"
        assert error.details["persona_name"] == "unknown-persona"

    def test_chat_llm_error(self):
        """Test ChatLLMError includes proper details."""
        # Arrange & Act
        error = ChatLLMError("API timeout", session_id="test-session")

        # Assert
        assert "API timeout" in str(error)
        assert error.code == "CHAT_LLM_ERROR"
        assert error.details["session_id"] == "test-session"

    def test_chat_message_error(self):
        """Test ChatMessageError includes proper details."""
        # Arrange & Act
        error = ChatMessageError("Invalid format", session_id="test-session")

        # Assert
        assert "Invalid format" in str(error)
        assert error.code == "CHAT_MESSAGE_ERROR"
        assert error.details["session_id"] == "test-session"
