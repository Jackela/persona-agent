"""Tests for ResponseGenerationStage."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from persona_agent.core.memory_store import MemoryStore
from persona_agent.core.persona_manager import PersonaManager
from persona_agent.core.pipeline.context import ChatContext, StageResult
from persona_agent.core.pipeline.stages.generation import ResponseGenerationStage
from persona_agent.utils.llm_client import LLMClient, LLMResponse


class TestResponseGenerationStage:
    """Test suite for ResponseGenerationStage."""

    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLMClient."""
        client = MagicMock(spec=LLMClient)
        client.chat = AsyncMock(return_value=LLMResponse("raw response", "model"))
        client.chat_stream = MagicMock(return_value=async_generator(["chunk1", "chunk2"]))
        return client

    @pytest.fixture
    def mock_persona_manager(self):
        """Create a mock PersonaManager."""
        manager = MagicMock(spec=PersonaManager)
        manager.apply_linguistic_style = MagicMock(return_value="styled response")
        return manager

    @pytest.fixture
    def mock_memory_store(self):
        """Create a mock MemoryStore."""
        store = MagicMock(spec=MemoryStore)
        store.store = AsyncMock()
        return store

    @pytest.fixture
    def stage(self, mock_llm_client, mock_persona_manager, mock_memory_store):
        """Create a ResponseGenerationStage instance with mocked dependencies."""
        return ResponseGenerationStage(
            llm_client=mock_llm_client,
            persona_manager=mock_persona_manager,
            memory_store=mock_memory_store,
        )

    @pytest.fixture
    def chat_context(self):
        """Create a ChatContext for testing."""
        return ChatContext(
            user_input="hello",
            session_id="session_123",
            messages=[{"role": "system", "content": "prompt"}],
        )

    @pytest.mark.asyncio
    async def test_generates_non_streaming_response(
        self, stage, mock_llm_client, chat_context
    ):
        """Test that non-streaming response is generated."""
        result = await stage.process(chat_context)

        mock_llm_client.chat.assert_called_once_with(chat_context.messages)
        assert chat_context.response == "styled response"
        assert isinstance(result, StageResult)
        assert result.should_continue is True

    @pytest.mark.asyncio
    async def test_applies_style(self, stage, mock_persona_manager, chat_context):
        """Test that linguistic style is applied to response."""
        await stage.process(chat_context)

        mock_persona_manager.apply_linguistic_style.assert_called_once_with(
            "raw response",
            use_kaomoji=True,
            use_nickname=True,
        )

    @pytest.mark.asyncio
    async def test_handles_streaming(self, stage, mock_llm_client, chat_context):
        """Test that streaming mode returns an async iterator."""
        chat_context.stream = True

        result = await stage.process(chat_context)

        assert result.should_continue is False
        assert chat_context.is_complete is True
        assert chat_context.response is not None

    @pytest.mark.asyncio
    async def test_streaming_stores_memory_after_consumption(
        self, stage, mock_llm_client, mock_memory_store, mock_persona_manager, chat_context
    ):
        """Test that streaming stores memory after iterator is consumed."""
        chat_context.stream = True

        await stage.process(chat_context)

        chunks = []
        async for chunk in chat_context.response:
            chunks.append(chunk)

        assert chunks == ["chunk1", "chunk2"]
        mock_memory_store.store.assert_called_once_with(
            session_id="session_123",
            user_message="hello",
            assistant_message="styled response",
        )
        mock_persona_manager.apply_linguistic_style.assert_called_once_with(
            "chunk1chunk2",
            use_kaomoji=True,
            use_nickname=True,
        )

    @pytest.mark.asyncio
    async def test_non_streaming_does_not_store_memory(
        self, stage, mock_memory_store, chat_context
    ):
        """Test that non-streaming path does not store memory in stage."""
        await stage.process(chat_context)

        mock_memory_store.store.assert_not_called()


async def async_generator(items):
    """Helper to create an async generator from a list."""
    for item in items:
        yield item
