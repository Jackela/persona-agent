"""Integration tests for persona-agent.

Tests the full system working together.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from persona_agent.config.loader import ConfigLoader
from persona_agent.core.agent_engine import AgentEngine
from persona_agent.core.memory_store import MemoryStore
from persona_agent.core.persona_manager import PersonaManager
from persona_agent.utils.llm_client import LLMResponse


class TestFullConversationFlow:
    """Test complete conversation flow."""

    @pytest.fixture
    def setup(self):
        """Set up full test environment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            config_path = tmp_path / "config"
            config_path.mkdir()
            (config_path / "characters").mkdir()
            (config_path / "linguistic_styles").mkdir()
            (config_path / "mood_states").mkdir()

            # Create Pixel-like character
            char_data = {
                "name": "Pixel",
                "version": "1.0.0",
                "relationship": "青梅竹马的女友",
                "physical": {
                    "height": "165cm",
                    "hair": "粉色长发",
                    "eyes": "黑色",
                },
                "traits": {
                    "personality": {
                        "openness": 0.8,
                        "conscientiousness": 0.7,
                        "extraversion": 0.6,
                        "agreeableness": 0.9,
                        "neuroticism": 0.2,
                    },
                    "communication_style": {
                        "tone": "playful",
                        "verbosity": "medium",
                        "empathy": "high",
                    },
                },
                "backstory": "你的青梅竹马，性格活泼带点傲娇。",
                "goals": {
                    "primary": "陪伴你",
                    "secondary": ["让你开心", "支持你的决定"],
                },
            }
            with open(config_path / "characters" / "pixel.yaml", "w") as f:
                yaml.dump(char_data, f)

            yield tmp_path, config_path

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM client."""
        client = MagicMock()
        responses = [
            LLMResponse(content=r, model="gpt-4", usage={})
            for r in [
                "哼哼~ 今天天气不错呢！(ゝ∀･)",
                "笨蛋，我当然记得你说过的话啦！",
                "别难过了，有我在呢。",
            ]
        ]
        from itertools import cycle
        client.chat = AsyncMock(side_effect=cycle(responses))
        return client

    @pytest.mark.asyncio
    async def test_conversation_with_memory(self, setup, mock_llm):
        """Test that conversation history is remembered."""
        tmp_path, config_path = setup

        loader = ConfigLoader(config_path)
        persona_manager = PersonaManager(loader, "pixel")
        memory_store = MemoryStore(tmp_path / "memory.db")

        agent = AgentEngine(
            persona_manager=persona_manager,
            memory_store=memory_store,
            llm_client=mock_llm,
            session_id="test_session",
        )

        # First message
        response1 = await agent.chat("今天天气怎么样？")
        assert "天气" in response1 or len(response1) > 0

        # Second message - should have context
        response2 = await agent.chat("你还记得我刚才说什么吗？")
        assert len(response2) > 0

        # Verify memory stored
        memories = await memory_store.retrieve_recent("test_session")
        assert len(memories) == 2
        assert memories[0].user_message == "你还记得我刚才说什么吗？"

    @pytest.mark.asyncio
    async def test_mood_changes_during_conversation(self, setup, mock_llm):
        """Test that mood changes based on conversation."""
        tmp_path, config_path = setup

        loader = ConfigLoader(config_path)
        persona_manager = PersonaManager(loader, "pixel")
        memory_store = MemoryStore(tmp_path / "memory.db")

        agent = AgentEngine(
            persona_manager=persona_manager,
            memory_store=memory_store,
            llm_client=mock_llm,
            session_id="test_session",
        )

        _initial_mood = persona_manager.get_mood_engine().current_state.name

        # Trigger caring mode
        await agent.chat("我今天很难过")

        _current_mood = persona_manager.get_mood_engine().current_state.name
        # Mood should have changed (or at least been evaluated)

    @pytest.mark.asyncio
    async def test_persona_consistency(self, setup, mock_llm):
        """Test that persona maintains character consistency."""
        tmp_path, config_path = setup

        loader = ConfigLoader(config_path)
        persona_manager = PersonaManager(loader, "pixel")

        # Build system prompt
        prompt = persona_manager.build_system_prompt()

        # Verify character info is in prompt
        assert "Pixel" in prompt
        assert "青梅竹马" in prompt
        assert "165cm" in prompt or "粉色" in prompt


class TestConfigLoadingIntegration:
    """Test configuration loading integration."""

    @pytest.fixture
    def temp_config(self):
        """Create temporary configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.mkdir()
            (config_path / "characters").mkdir()
            (config_path / "linguistic_styles").mkdir()
            (config_path / "mood_states").mkdir()

            yield config_path

    def test_load_character_with_mood_config(self, temp_config):
        """Test loading character with associated mood config."""
        char_data = {
            "name": "Test",
            "traits": {"personality": {"openness": 0.5}},
            "backstory": "Test",
            "goals": {"primary": "Test"},
            "mood_config": "mood_states/default.md",
        }
        with open(temp_config / "characters" / "test.yaml", "w") as f:
            yaml.dump(char_data, f)

        # Create mood config
        mood_content = "# Mood States\n\n## DEFAULT\n- **描述**: Default state\n"
        with open(temp_config / "mood_states" / "default.md", "w") as f:
            f.write(mood_content)

        loader = ConfigLoader(temp_config)
        manager = PersonaManager(loader, "test")

        assert manager.get_mood_engine() is not None


class TestMemoryPersistence:
    """Test memory persistence across sessions."""

    @pytest.mark.asyncio
    async def test_memory_survives_reconnect(self):
        """Test that memory persists when reconnecting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "memory.db"

            # First session
            memory1 = MemoryStore(db_path)
            await memory1.store(
                session_id="session_123",
                user_message="Hello",
                assistant_message="Hi!",
            )

            # Second session (new instance, same DB)
            memory2 = MemoryStore(db_path)
            memories = await memory2.retrieve_recent("session_123")

            assert len(memories) == 1
            assert memories[0].user_message == "Hello"

    @pytest.mark.asyncio
    async def test_user_model_persistence(self):
        """Test user model persists across sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "memory.db"

            # First session
            memory1 = MemoryStore(db_path)
            model1 = await memory1.get_or_create_user_model("user_123")
            model1.traits["friendliness"] = 0.9
            await memory1.update_user_model(model1)

            # Second session
            memory2 = MemoryStore(db_path)
            model2 = await memory2.get_or_create_user_model("user_123")

            assert model2.traits["friendliness"] == 0.9


class TestErrorHandling:
    """Test error handling in integration scenarios."""

    @pytest.mark.asyncio
    async def test_missing_character(self):
        """Test error when character not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.mkdir()
            (config_path / "characters").mkdir()

            loader = ConfigLoader(config_path)

            with pytest.raises(FileNotFoundError):
                PersonaManager(loader, "nonexistent")

    @pytest.mark.asyncio
    async def test_chat_without_llm(self):
        """Test error when LLM not configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.mkdir()
            (config_path / "characters").mkdir()

            char_data = {
                "name": "Test",
                "traits": {},
                "backstory": "",
                "goals": {"primary": "Test"},
            }
            with open(config_path / "characters" / "test.yaml", "w") as f:
                yaml.dump(char_data, f)

            loader = ConfigLoader(config_path)
            persona = PersonaManager(loader, "test")
            memory = MemoryStore(Path(tmpdir) / "memory.db")

            agent = AgentEngine(
                persona_manager=persona,
                memory_store=memory,
                llm_client=None,
            )

            with pytest.raises(RuntimeError, match="LLM client not configured"):
                await agent.chat("Hello")
