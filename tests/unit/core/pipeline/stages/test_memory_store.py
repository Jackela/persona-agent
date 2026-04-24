"""Tests for MemoryStorageStage."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from persona_agent.core.memory_store import MemoryStore
from persona_agent.core.pipeline.context import ChatContext, StageResult
from persona_agent.core.pipeline.stages.memory_store import MemoryStorageStage


class TestMemoryStorageStage:
    """Test suite for MemoryStorageStage."""

    @pytest.fixture
    def mock_memory_store(self):
        """Create a mock MemoryStore."""
        store = MagicMock(spec=MemoryStore)
        store.store = AsyncMock()
        return store

    @pytest.fixture
    def stage(self, mock_memory_store):
        """Create a MemoryStorageStage instance with mocked dependencies."""
        return MemoryStorageStage(memory_store=mock_memory_store)

    @pytest.fixture
    def chat_context(self):
        """Create a ChatContext for testing."""
        return ChatContext(
            user_input="hello",
            session_id="session_123",
        )

    @pytest.mark.asyncio
    async def test_stores_non_streaming_response(self, stage, mock_memory_store, chat_context):
        """Test that non-streaming response is stored in memory."""
        chat_context.response = "assistant response"

        result = await stage.process(chat_context)

        mock_memory_store.store.assert_called_once_with(
            session_id="session_123",
            user_message="hello",
            assistant_message="assistant response",
        )
        assert isinstance(result, StageResult)
        assert result.should_continue is True

    @pytest.mark.asyncio
    async def test_skips_storage_for_streaming(self, stage, mock_memory_store, chat_context):
        """Test that streaming responses skip storage."""
        chat_context.stream = True
        chat_context.response = "streaming response"

        result = await stage.process(chat_context)

        mock_memory_store.store.assert_not_called()
        assert result.should_continue is True

    @pytest.mark.asyncio
    async def test_skips_storage_when_no_response(self, stage, mock_memory_store, chat_context):
        """Test that storage is skipped when response is None."""
        chat_context.response = None

        result = await stage.process(chat_context)

        mock_memory_store.store.assert_not_called()
        assert result.should_continue is True

    @pytest.mark.asyncio
    async def test_skips_storage_when_response_is_iterator(
        self, stage, mock_memory_store, chat_context
    ):
        """Test that storage is skipped when response is an async iterator."""

        async def fake_iterator():
            yield "chunk"

        chat_context.response = fake_iterator()

        result = await stage.process(chat_context)

        mock_memory_store.store.assert_not_called()
        assert result.should_continue is True
