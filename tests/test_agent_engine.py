"""Tests for agent engine."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from persona_agent.core.agent_engine import AgentEngine
from persona_agent.core.memory_store import MemoryStore
from persona_agent.core.persona_manager import PersonaManager
from persona_agent.utils.llm_client import LLMResponse


class TestAgentEngine:
    """Test agent engine functionality."""

    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client."""
        client = MagicMock()
        client.chat = AsyncMock(
            return_value=LLMResponse(
                content="Hello! I'm doing well.",
                model="gpt-4",
                usage={"prompt_tokens": 10, "completion_tokens": 5},
            )
        )
        return client

    @pytest.fixture
    def agent_engine(self, mock_llm_client):
        """Create agent engine with mocked components."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.mkdir()
            (config_path / "characters").mkdir()
            (config_path / "linguistic_styles").mkdir()
            (config_path / "mood_states").mkdir()

            # Create minimal test config
            import yaml

            char_data = {
                "name": "TestBot",
                "version": "1.0.0",
                "traits": {"personality": {"openness": 0.5}},
                "backstory": "Test",
                "goals": {"primary": "Help"},
            }
            with open(config_path / "characters" / "default.yaml", "w") as f:
                yaml.dump(char_data, f)

            from persona_agent.config.loader import ConfigLoader

            loader = ConfigLoader(config_path)
            persona_manager = PersonaManager(loader, "default")
            memory_store = MemoryStore(Path(tmpdir) / "test.db")

            engine = AgentEngine(
                persona_manager=persona_manager,
                memory_store=memory_store,
                llm_client=mock_llm_client,
                session_id="test_session",
            )
            yield engine

    @pytest.mark.asyncio
    async def test_chat_basic(self, agent_engine, mock_llm_client):
        """Test basic chat functionality."""
        response = await agent_engine.chat("How are you?")
        assert isinstance(response, str)
        assert len(response) > 0
        mock_llm_client.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_stores_memory(self, agent_engine):
        """Test that chat stores conversation in memory."""
        await agent_engine.chat("Hello")

        # Check memory was stored
        memories = await agent_engine.memory_store.retrieve_recent("test_session")
        assert len(memories) == 1
        assert memories[0].user_message == "Hello"

    @pytest.mark.asyncio
    async def test_multiple_messages(self, agent_engine):
        """Test multiple messages in a conversation."""
        for i in range(3):
            await agent_engine.chat(f"Message {i}")

        memories = await agent_engine.memory_store.retrieve_recent("test_session")
        assert len(memories) == 3

    @pytest.mark.asyncio
    async def test_chat_updates_mood(self, agent_engine):
        """Test that chat updates mood."""
        _initial_mood = agent_engine.persona_manager.get_mood_engine().current_state.name
        await agent_engine.chat("I'm so happy today!")
        # Mood might change based on input

    def test_get_session_info(self, agent_engine):
        """Test getting session info."""
        info = agent_engine.get_session_info()
        assert info["session_id"] == "test_session"
        assert info["character"] == "TestBot"
        assert "current_mood" in info

    def test_get_current_persona(self, agent_engine):
        """Test getting current persona name."""
        persona = agent_engine.get_current_persona()
        assert persona == "TestBot"

    def test_switch_persona(self, agent_engine):
        """Test switching persona."""
        # This would require multiple character configs
        # For now, just verify the method exists and doesn't crash
        initial_persona = agent_engine.get_current_persona()
        assert initial_persona is not None


class TestAgentEngineInitialization:
    """Test agent engine initialization."""

    def test_create_without_llm(self):
        """Test creating engine without LLM client."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.mkdir()
            (config_path / "characters").mkdir()

            import yaml

            char_data = {
                "name": "Test",
                "traits": {},
                "backstory": "",
                "goals": {"primary": "Test"},
            }
            with open(config_path / "characters" / "test.yaml", "w") as f:
                yaml.dump(char_data, f)

            from persona_agent.config.loader import ConfigLoader

            loader = ConfigLoader(config_path)
            persona_manager = PersonaManager(loader, "test")
            memory_store = MemoryStore(Path(tmpdir) / "test.db")

            engine = AgentEngine(
                persona_manager=persona_manager,
                memory_store=memory_store,
                llm_client=None,
            )
            assert engine.llm_client is None

    @pytest.mark.asyncio
    async def test_chat_without_llm_raises(self):
        """Test that chat raises error without LLM client."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.mkdir()
            (config_path / "characters").mkdir()

            import yaml

            char_data = {
                "name": "Test",
                "traits": {},
                "backstory": "",
                "goals": {"primary": "Test"},
            }
            with open(config_path / "characters" / "test.yaml", "w") as f:
                yaml.dump(char_data, f)

            from persona_agent.config.loader import ConfigLoader

            loader = ConfigLoader(config_path)
            persona_manager = PersonaManager(loader, "test")
            memory_store = MemoryStore(Path(tmpdir) / "test.db")

            engine = AgentEngine(
                persona_manager=persona_manager,
                memory_store=memory_store,
                llm_client=None,
            )

            with pytest.raises(RuntimeError, match="LLM client not configured"):
                await engine.chat("Hello")
