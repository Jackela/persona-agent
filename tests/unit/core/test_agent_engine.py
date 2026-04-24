"""Tests for agent_engine module."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from persona_agent.core.agent_engine import AgentEngine


class TestAgentEngine:
    """Test suite for AgentEngine."""

    @pytest.fixture
    def mock_persona_manager(self):
        """Mock persona manager."""
        manager = MagicMock()
        manager.get_character.return_value = MagicMock(name="TestCharacter")
        mood_engine = MagicMock()
        mood_engine.current_state.name = "happy"
        manager.get_mood_engine.return_value = mood_engine
        manager.build_system_prompt.return_value = "System prompt"
        manager.apply_linguistic_style.return_value = "Styled response"
        return manager

    @pytest.fixture
    def mock_memory_store(self):
        """Mock memory store."""
        store = AsyncMock()
        store.retrieve_recent.return_value = []
        store.store.return_value = 1
        return store

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM client."""
        client = AsyncMock()
        response = MagicMock()
        response.content = "Hello, I'm an AI assistant."
        client.chat.return_value = response

        async def mock_stream(*args, **kwargs):
            yield "Hello"
            yield ", "
            yield "world!"

        client.chat_stream = mock_stream
        return client

    @pytest.fixture
    def mock_skill_registry(self):
        """Mock skill registry."""
        registry = AsyncMock()
        result = MagicMock()
        result.success = False
        result.response = None
        registry.execute_matching.return_value = result
        return registry

    @pytest.fixture
    def mock_mcp_client(self):
        """Mock MCP client."""
        return MagicMock()

    @pytest.fixture
    def agent_engine(
        self,
        mock_persona_manager,
        mock_memory_store,
        mock_llm_client,
        mock_skill_registry,
        mock_mcp_client,
    ):
        """Create an AgentEngine with mocked dependencies."""
        return AgentEngine(
            persona_manager=mock_persona_manager,
            memory_store=mock_memory_store,
            llm_client=mock_llm_client,
            session_id="test-session-123",
            skill_registry=mock_skill_registry,
            mcp_client=mock_mcp_client,
        )

    def test_initialization(self, agent_engine):
        """Test engine initialization."""
        assert agent_engine.session_id == "test-session-123"
        assert agent_engine.persona_manager is not None
        assert agent_engine.memory_store is not None
        assert agent_engine.llm_client is not None

    def test_initialization_generates_session_id(self):
        """Test that session ID is auto-generated if not provided."""
        with (
            patch("persona_agent.core.agent_engine.PersonaManager"),
            patch("persona_agent.core.agent_engine.MemoryStore"),
            patch("persona_agent.core.agent_engine.get_registry"),
            patch("persona_agent.core.agent_engine.get_mcp_client"),
        ):
            engine = AgentEngine()

            # Verify UUID format
            assert len(engine.session_id) == 36
            uuid.UUID(engine.session_id)  # Should not raise

    @pytest.mark.asyncio
    async def test_chat_without_llm_client(self, agent_engine):
        """Test chat raises error when LLM client not configured."""
        agent_engine.llm_client = None

        with pytest.raises(RuntimeError, match="LLM client not configured"):
            await agent_engine.chat("Hello")

    @pytest.mark.asyncio
    async def test_chat_basic(self, agent_engine, mock_llm_client, mock_memory_store):
        """Test basic chat functionality."""
        response = await agent_engine.chat("Hello")

        assert response == "Styled response"
        mock_llm_client.chat.assert_called_once()

        # Verify memory storage
        mock_memory_store.store.assert_called_once()
        call_args = mock_memory_store.store.call_args
        assert call_args[1]["user_message"] == "Hello"
        assert call_args[1]["assistant_message"] == "Styled response"

    @pytest.mark.asyncio
    async def test_chat_with_skill_match(self, agent_engine, mock_skill_registry):
        """Test chat with skill matching."""
        # Setup skill to match
        skill_result = MagicMock()
        skill_result.success = True
        skill_result.response = "Skill handled this!"
        mock_skill_registry.execute_matching.return_value = skill_result

        response = await agent_engine.chat("What's the weather?")

        assert response == "Skill handled this!"
        # LLM should not be called when skill handles it
        agent_engine.llm_client.chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_chat_stream(self, agent_engine):
        """Test streaming chat."""
        chunks = []
        async for chunk in await agent_engine.chat("Hello", stream=True):
            chunks.append(chunk)

        assert chunks == ["Hello", ", ", "world!"]

    @pytest.mark.asyncio
    async def test_chat_with_history(self, agent_engine, mock_memory_store):
        """Test chat includes conversation history."""
        # Setup some history

        mock_memory = MagicMock()
        mock_memory.user_message = "Previous message"
        mock_memory.assistant_message = "Previous response"
        mock_memory_store.retrieve_recent.return_value = [mock_memory]

        await agent_engine.chat("New message")

        # Verify messages include history
        call_args = agent_engine.llm_client.chat.call_args
        # Handle both positional and keyword arguments
        if call_args[1] and "messages" in call_args[1]:
            messages = call_args[1]["messages"]
        else:
            messages = call_args[0][0]

        assert len(messages) > 2  # System + history + current
        assert messages[0]["role"] == "system"

    def test_switch_persona(self, agent_engine, mock_persona_manager):
        """Test switching personas."""
        agent_engine.switch_persona("new_character")

        mock_persona_manager.load_character.assert_called_once_with("new_character")

    def test_get_current_persona(self, agent_engine, mock_persona_manager):
        """Test getting current persona name."""
        char = MagicMock()
        char.name = "TestPersona"
        mock_persona_manager.get_character.return_value = char

        name = agent_engine.get_current_persona()

        assert name == "TestPersona"

    def test_get_current_persona_none(self, agent_engine, mock_persona_manager):
        """Test getting persona when none loaded."""
        mock_persona_manager.get_character.return_value = None

        name = agent_engine.get_current_persona()

        assert name is None

    def test_get_session_info(self, agent_engine):
        """Test getting session information."""
        info = agent_engine.get_session_info()

        assert info["session_id"] == "test-session-123"
        assert "character" in info
        assert "current_mood" in info


class TestAgentEngineIntegration:
    """Integration-style tests for AgentEngine."""

    @pytest.mark.asyncio
    async def test_full_conversation_flow(self):
        """Test a complete conversation flow."""
        with (
            patch("persona_agent.core.agent_engine.PersonaManager"),
            patch("persona_agent.core.agent_engine.MemoryStore"),
            patch("persona_agent.core.agent_engine.get_registry"),
            patch("persona_agent.core.agent_engine.get_mcp_client"),
        ):
            # Setup mocks
            persona_manager = MagicMock()
            persona_manager.get_character.return_value = MagicMock(name="TestCharacter")
            mood_engine = MagicMock()
            mood_engine.current_state.name = "neutral"
            persona_manager.get_mood_engine.return_value = mood_engine
            persona_manager.build_system_prompt.return_value = "System"
            persona_manager.apply_linguistic_style.return_value = lambda x: x

            memory_store = AsyncMock()
            memory_store.retrieve_recent.return_value = []
            memory_store.store.return_value = 1

            llm_client = AsyncMock()
            response = MagicMock()
            response.content = "Response"
            llm_client.chat.return_value = response

            skill_registry = AsyncMock()
            skill_result = MagicMock()
            skill_result.success = False
            skill_registry.execute_matching.return_value = skill_result

            # Create engine
            engine = AgentEngine(
                persona_manager=persona_manager,
                memory_store=memory_store,
                llm_client=llm_client,
                skill_registry=skill_registry,
            )

            # Multiple exchanges
            response1 = await engine.chat("Hello")
            response2 = await engine.chat("How are you?")

            assert response1 is not None
            assert response2 is not None

            # Verify memories were stored
            assert memory_store.store.call_count == 2
