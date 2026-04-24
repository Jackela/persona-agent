"""Tests for ContextPreparationStage."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from persona_agent.core.memory_store import Memory, MemoryStore
from persona_agent.core.persona_manager import PersonaManager
from persona_agent.core.pipeline.context import ChatContext, StageResult
from persona_agent.core.pipeline.stages.context_prep import ContextPreparationStage


class TestContextPreparationStage:
    """Test suite for ContextPreparationStage."""

    @pytest.fixture
    def mock_persona_manager(self):
        """Create a mock PersonaManager."""
        manager = MagicMock(spec=PersonaManager)
        manager.update_mood = MagicMock()
        manager.build_system_prompt = MagicMock(return_value="system prompt")
        return manager

    @pytest.fixture
    def mock_memory_store(self):
        """Create a mock MemoryStore."""
        store = MagicMock(spec=MemoryStore)
        store.retrieve_recent = AsyncMock(return_value=[])
        return store

    @pytest.fixture
    def stage(self, mock_persona_manager, mock_memory_store):
        """Create a ContextPreparationStage instance with mocked dependencies."""
        return ContextPreparationStage(
            persona_manager=mock_persona_manager,
            memory_store=mock_memory_store,
            memory_limit=10,
        )

    @pytest.fixture
    def chat_context(self):
        """Create a ChatContext for testing."""
        return ChatContext(
            user_input="hello",
            session_id="session_123",
        )

    @pytest.mark.asyncio
    async def test_updates_mood(self, stage, mock_persona_manager, chat_context):
        """Test that mood is updated based on user input."""
        await stage.process(chat_context)

        mock_persona_manager.update_mood.assert_called_once_with("hello")

    @pytest.mark.asyncio
    async def test_builds_system_prompt(self, stage, mock_persona_manager, chat_context):
        """Test that system prompt is built and added to messages."""
        result = await stage.process(chat_context)

        mock_persona_manager.build_system_prompt.assert_called_once()
        assert chat_context.messages[0] == {"role": "system", "content": "system prompt"}
        assert isinstance(result, StageResult)
        assert result.should_continue is True

    @pytest.mark.asyncio
    async def test_retrieves_memories(self, stage, mock_memory_store, chat_context):
        """Test that recent memories are retrieved."""
        await stage.process(chat_context)

        mock_memory_store.retrieve_recent.assert_called_once_with("session_123", limit=10)

    @pytest.mark.asyncio
    async def test_assembles_messages_correctly(
        self, stage, mock_persona_manager, mock_memory_store, chat_context
    ):
        """Test that messages are assembled in correct order."""
        memories = [
            Memory(
                id="1",
                session_id="session_123",
                timestamp=1.0,
                user_message="past user msg",
                assistant_message="past assistant msg",
            ),
        ]
        mock_memory_store.retrieve_recent.return_value = memories

        result = await stage.process(chat_context)

        assert chat_context.messages == [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "past user msg"},
            {"role": "assistant", "content": "past assistant msg"},
            {"role": "user", "content": "hello"},
        ]
        assert result.should_continue is True

    @pytest.mark.asyncio
    async def test_empty_memories(self, stage, mock_persona_manager, chat_context):
        """Test behavior when no memories exist."""
        result = await stage.process(chat_context)

        assert chat_context.messages == [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "hello"},
        ]
        assert result.should_continue is True

    @pytest.mark.asyncio
    async def test_multiple_memories(self, stage, mock_memory_store, chat_context):
        """Test assembly with multiple memories."""
        memories = [
            Memory(
                id="1",
                session_id="session_123",
                timestamp=1.0,
                user_message="msg1",
                assistant_message="resp1",
            ),
            Memory(
                id="2",
                session_id="session_123",
                timestamp=2.0,
                user_message="msg2",
                assistant_message="resp2",
            ),
        ]
        mock_memory_store.retrieve_recent.return_value = memories

        await stage.process(chat_context)

        assert chat_context.messages == [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "resp1"},
            {"role": "user", "content": "msg2"},
            {"role": "assistant", "content": "resp2"},
            {"role": "user", "content": "hello"},
        ]
