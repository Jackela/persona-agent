"""Integration tests for chat workflows.

Tests complete chat session flows including session creation, messaging,
persona switching, session persistence, and error recovery.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock

from persona_agent.repositories.models import Session
from persona_agent.services.chat_service import (
    ChatService,
    ChatSessionNotFoundError,
    ChatPersonaNotFoundError,
    ChatMessageError,
)
from persona_agent.services.session_service import SessionService
from persona_agent.utils.llm_client import LLMResponse


@pytest.mark.asyncio
class TestFullChatSessionFlow:
    """Test complete chat session flows end-to-end."""

    async def test_create_session_and_send_messages(self, chat_service: ChatService):
        """Test creating a new session and sending multiple messages."""
        # Create a new session
        session_id = await chat_service.create_new_session(persona_name="default")
        assert session_id is not None
        assert isinstance(session_id, str)

        # Send first message
        response1 = await chat_service.send_message(session_id, "Hello!")
        assert response1 == "This is a test response from the mock LLM."

        # Send second message
        response2 = await chat_service.send_message(session_id, "How are you?")
        assert response2 == "This is a test response from the mock LLM."

        # Verify conversation history
        history = await chat_service.get_conversation_history(session_id)
        assert len(history) == 4  # 2 user + 2 assistant messages
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello!"
        assert history[1]["role"] == "assistant"
        assert history[2]["role"] == "user"
        assert history[2]["content"] == "How are you?"
        assert history[3]["role"] == "assistant"

    async def test_create_session_with_custom_id(self, chat_service: ChatService):
        """Test creating a session with a custom ID."""
        custom_id = "my-custom-session-id"
        session_id = await chat_service.create_new_session(
            persona_name="default", session_id=custom_id
        )

        assert session_id == custom_id

        # Verify session exists
        info = await chat_service.get_session_info(session_id)
        assert info["session_id"] == custom_id

    async def test_session_with_multiple_messages_persisted(self, chat_service: ChatService):
        """Test that multiple messages are correctly persisted in a session."""
        session_id = await chat_service.create_new_session(persona_name="companion")

        # Send multiple messages
        for i in range(5):
            response = await chat_service.send_message(session_id, f"Message {i}")
            assert response is not None

        # Get conversation history
        history = await chat_service.get_conversation_history(session_id)
        assert len(history) == 10  # 5 user + 5 assistant messages

        # Verify order
        for i in range(5):
            assert history[i * 2]["content"] == f"Message {i}"
            assert history[i * 2]["role"] == "user"
            assert history[i * 2 + 1]["role"] == "assistant"

    async def test_session_info_returns_correct_data(self, chat_service: ChatService):
        """Test that session info returns correct metadata."""
        session_id = await chat_service.create_new_session(persona_name="mentor")

        # Send a message
        await chat_service.send_message(session_id, "Test message")

        # Get session info
        info = await chat_service.get_session_info(session_id)

        assert info["session_id"] == session_id
        assert info["persona_name"] == "mentor"
        assert info["message_count"] == 2  # user + assistant
        assert isinstance(info["first_activity"], datetime)
        assert isinstance(info["last_activity"], datetime)
        assert info["last_activity"] >= info["first_activity"]


@pytest.mark.asyncio
class TestPersonaSwitchingFlow:
    """Test persona switching within chat sessions."""

    async def test_switch_persona_mid_conversation(self, chat_service: ChatService):
        """Test switching persona during an active conversation."""
        session_id = await chat_service.create_new_session(persona_name="default")
        await chat_service.send_message(session_id, "Hello")

        info = await chat_service.get_session_info(session_id)
        assert info["persona_name"] == "default"

        result = await chat_service.switch_persona(session_id, "companion")
        assert "switched to 'companion'" in result

        response = await chat_service.send_message(session_id, "How are you?")
        assert response is not None

    async def test_switch_persona_multiple_times(self, chat_service: ChatService):
        """Test switching persona multiple times in one session."""
        session_id = await chat_service.create_new_session(persona_name="default")

        personas = ["default", "companion", "mentor", "companion"]

        for persona in personas:
            result = await chat_service.switch_persona(session_id, persona)
            assert persona in result

        history = await chat_service.get_conversation_history(session_id, include_system=True)
        assert any("Persona switched to" in msg.get("content", "") for msg in history)

    async def test_switch_persona_with_transition_message(self, chat_service: ChatService):
        """Test that transition message is added when switching personas."""
        session_id = await chat_service.create_new_session(persona_name="default")
        initial_history = await chat_service.get_conversation_history(
            session_id, include_system=True
        )
        initial_count = len(initial_history)

        # Switch with transition message
        await chat_service.switch_persona(session_id, "companion", add_transition_message=True)

        # Verify transition message was added
        history = await chat_service.get_conversation_history(session_id, include_system=True)
        assert len(history) == initial_count + 1
        assert "Persona switched to" in history[-1]["content"]
        assert history[-1]["role"] == "system"

    async def test_switch_persona_without_transition_message(self, chat_service: ChatService):
        """Test switching persona without transition message."""
        session_id = await chat_service.create_new_session(persona_name="default")
        initial_history = await chat_service.get_conversation_history(
            session_id, include_system=True
        )
        initial_count = len(initial_history)

        # Switch without transition message
        await chat_service.switch_persona(session_id, "mentor", add_transition_message=False)

        # Verify no transition message was added
        history = await chat_service.get_conversation_history(session_id, include_system=True)
        assert len(history) == initial_count

    async def test_switch_to_nonexistent_persona_fails(self, chat_service: ChatService):
        """Test that switching to non-existent persona raises error."""
        session_id = await chat_service.create_new_session(persona_name="default")

        with pytest.raises(ChatPersonaNotFoundError) as exc_info:
            await chat_service.switch_persona(session_id, "nonexistent")

        assert "nonexistent" in str(exc_info.value)


@pytest.mark.asyncio
class TestSessionPersistenceFlow:
    """Test session persistence across operations."""

    async def test_session_persists_after_closing_service(
        self, temp_config_dir, test_characters, mock_llm_client
    ):
        """Test that session data persists after service is closed and reopened."""
        from persona_agent.repositories import SessionRepository
        from persona_agent.services.character_service import CharacterService
        from persona_agent.services.session_service import SessionService

        db_path = temp_config_dir / "persistent_test.db"

        # Create first service instance
        char_service = CharacterService(config_dir=temp_config_dir)
        repo1 = SessionRepository(db_path)
        await repo1.connect()
        session_service1 = SessionService(db_path, session_repo=repo1)

        chat_service1 = ChatService(
            character_service=char_service,
            session_service=session_service1,
            llm_client=mock_llm_client,
            db_path=db_path,
        )

        # Create session and send message
        session_id = await chat_service1.create_new_session(persona_name="default")
        await chat_service1.send_message(session_id, "Hello from first service")

        # Close first service
        await chat_service1.close()

        # Create second service instance with same database
        repo2 = SessionRepository(db_path)
        await repo2.connect()
        session_service2 = SessionService(db_path, session_repo=repo2)

        chat_service2 = ChatService(
            character_service=char_service,
            session_service=session_service2,
            llm_client=mock_llm_client,
            db_path=db_path,
        )

        # Verify session persisted
        info = await chat_service2.get_session_info(session_id)
        assert info["session_id"] == session_id
        assert info["message_count"] == 2  # user + assistant

        history = await chat_service2.get_conversation_history(session_id)
        assert history[0]["content"] == "Hello from first service"

        await chat_service2.close()

    async def test_multiple_sessions_isolated(self, chat_service: ChatService):
        """Test that multiple sessions are isolated from each other."""
        # Create multiple sessions
        session1 = await chat_service.create_new_session(persona_name="default")
        session2 = await chat_service.create_new_session(persona_name="companion")
        session3 = await chat_service.create_new_session(persona_name="mentor")

        # Send different messages to each session
        await chat_service.send_message(session1, "Message for session 1")
        await chat_service.send_message(session2, "Message for session 2")
        await chat_service.send_message(session3, "Message for session 3")

        # Verify each session has correct content
        history1 = await chat_service.get_conversation_history(session1)
        history2 = await chat_service.get_conversation_history(session2)
        history3 = await chat_service.get_conversation_history(session3)

        assert history1[0]["content"] == "Message for session 1"
        assert history2[0]["content"] == "Message for session 2"
        assert history3[0]["content"] == "Message for session 3"

        # Verify personas
        info1 = await chat_service.get_session_info(session1)
        info2 = await chat_service.get_session_info(session2)
        info3 = await chat_service.get_session_info(session3)

        assert info1["persona_name"] == "default"
        assert info2["persona_name"] == "companion"
        assert info3["persona_name"] == "mentor"

    async def test_conversation_history_persists_updates(self, chat_service: ChatService):
        """Test that conversation history is updated and persisted correctly."""
        session_id = await chat_service.create_new_session(persona_name="default")

        # Send messages in sequence
        messages = ["First", "Second", "Third"]
        for msg in messages:
            await chat_service.send_message(session_id, msg)

            # Verify history after each message
            history = await chat_service.get_conversation_history(session_id)
            assert len(history) == len(messages[: messages.index(msg) + 1]) * 2

        # Final verification
        final_history = await chat_service.get_conversation_history(session_id)
        assert len(final_history) == 6  # 3 user + 3 assistant

        for i, msg in enumerate(messages):
            assert final_history[i * 2]["content"] == msg

    async def test_session_last_activity_updated(self, chat_service: ChatService):
        """Test that session last_activity is updated after each message."""
        session_id = await chat_service.create_new_session(persona_name="default")

        # Get initial last_activity
        info1 = await chat_service.get_session_info(session_id)
        first_activity = info1["last_activity"]

        # Send message
        import asyncio

        await asyncio.sleep(0.01)  # Small delay to ensure timestamp changes
        await chat_service.send_message(session_id, "Test")

        # Verify last_activity was updated
        info2 = await chat_service.get_session_info(session_id)
        assert info2["last_activity"] > first_activity


@pytest.mark.asyncio
class TestErrorRecoveryFlow:
    """Test error handling and recovery in chat workflows."""

    async def test_send_message_to_nonexistent_session_fails(self, chat_service: ChatService):
        """Test that sending to non-existent session raises appropriate error."""
        with pytest.raises(ChatSessionNotFoundError) as exc_info:
            await chat_service.send_message("nonexistent-session", "Hello")

        assert "nonexistent-session" in str(exc_info.value)
        assert exc_info.value.code == "CHAT_SESSION_NOT_FOUND"

    async def test_create_session_with_nonexistent_persona_fails(self, chat_service: ChatService):
        """Test that creating session with invalid persona raises error."""
        with pytest.raises(ChatPersonaNotFoundError) as exc_info:
            await chat_service.create_new_session(persona_name="invalid-persona")

        assert "invalid-persona" in str(exc_info.value)
        assert exc_info.value.code == "CHAT_PERSONA_NOT_FOUND"

    async def test_empty_message_raises_error(self, chat_service: ChatService):
        """Test that sending empty message raises appropriate error."""
        session_id = await chat_service.create_new_session(persona_name="default")

        with pytest.raises(ChatMessageError) as exc_info:
            await chat_service.send_message(session_id, "")

        assert "cannot be empty" in str(exc_info.value)

    async def test_whitespace_message_raises_error(self, chat_service: ChatService):
        """Test that sending whitespace-only message raises error."""
        session_id = await chat_service.create_new_session(persona_name="default")

        with pytest.raises(ChatMessageError) as exc_info:
            await chat_service.send_message(session_id, "   \n\t  ")

        assert "cannot be empty" in str(exc_info.value)

    async def test_get_history_for_nonexistent_session_fails(self, chat_service: ChatService):
        """Test that getting history for non-existent session raises error."""
        with pytest.raises(ChatSessionNotFoundError) as exc_info:
            await chat_service.get_conversation_history("nonexistent")

        assert "nonexistent" in str(exc_info.value)

    async def test_get_info_for_nonexistent_session_fails(self, chat_service: ChatService):
        """Test that getting info for non-existent session raises error."""
        with pytest.raises(ChatSessionNotFoundError) as exc_info:
            await chat_service.get_session_info("nonexistent")

        assert "nonexistent" in str(exc_info.value)

    async def test_switch_persona_for_nonexistent_session_fails(self, chat_service: ChatService):
        """Test that switching persona for non-existent session raises error."""
        with pytest.raises(ChatSessionNotFoundError) as exc_info:
            await chat_service.switch_persona("nonexistent", "companion")

        assert "nonexistent" in str(exc_info.value)

    async def test_recover_from_llm_error(self, chat_service: ChatService):
        """Test that session remains valid after LLM error."""
        # Create session
        session_id = await chat_service.create_new_session(persona_name="default")
        await chat_service.send_message(session_id, "First message")

        # Simulate LLM error
        chat_service._llm_client.chat.side_effect = Exception("LLM API Error")

        # Try to send message (should fail)
        from persona_agent.services.chat_service import ChatLLMError

        with pytest.raises(ChatLLMError):
            await chat_service.send_message(session_id, "This will fail")

        # Restore LLM client
        async def mock_chat(*args, **kwargs):
            return LLMResponse(
                content="Recovered response",
                model="gpt-4-test",
                usage={},
            )

        chat_service._llm_client.chat = Mock(side_effect=mock_chat)

        # Should be able to send message again
        response = await chat_service.send_message(session_id, "After recovery")
        assert response == "Recovered response"

        # Verify session history is intact
        history = await chat_service.get_conversation_history(session_id)
        assert len(history) == 4  # 2 before error + 2 after recovery

    async def test_session_not_corrupted_by_failed_message(self, chat_service: ChatService):
        """Test that failed message doesn't corrupt session state."""
        session_id = await chat_service.create_new_session(persona_name="default")

        # Send initial message
        await chat_service.send_message(session_id, "Initial")
        initial_history = await chat_service.get_conversation_history(session_id)
        initial_count = len(initial_history)

        # Simulate error
        chat_service._llm_client.chat.side_effect = Exception("Network error")

        from persona_agent.services.chat_service import ChatLLMError

        with pytest.raises(ChatLLMError):
            await chat_service.send_message(session_id, "This fails")

        # Restore LLM
        async def mock_chat(*args, **kwargs):
            return LLMResponse(content="OK", model="gpt-4-test", usage={})

        chat_service._llm_client.chat = Mock(side_effect=mock_chat)

        # Verify session is still intact
        history = await chat_service.get_conversation_history(session_id)
        assert len(history) == initial_count  # Should not have added failed message
