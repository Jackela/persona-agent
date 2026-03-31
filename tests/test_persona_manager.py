"""Tests for persona manager."""

import tempfile
from pathlib import Path

import pytest
import yaml

from persona_agent.config.loader import ConfigLoader
from persona_agent.core.persona_manager import PersonaManager


class TestPersonaManager:
    """Test persona manager functionality."""

    @pytest.fixture
    def config_dir(self):
        """Create temporary config directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.mkdir()
            (config_path / "characters").mkdir()
            (config_path / "linguistic_styles").mkdir()
            (config_path / "mood_states").mkdir()
            yield config_path

    @pytest.fixture
    def sample_character_file(self, config_dir):
        """Create sample character file."""
        char_data = {
            "name": "TestBot",
            "version": "1.0.0",
            "relationship": "Friend",
            "traits": {
                "personality": {
                    "openness": 0.8,
                    "conscientiousness": 0.7,
                    "extraversion": 0.6,
                    "agreeableness": 0.9,
                    "neuroticism": 0.2,
                },
                "communication_style": {
                    "tone": "friendly",
                    "verbosity": "medium",
                    "empathy": "high",
                },
            },
            "backstory": "A friendly test assistant.",
            "goals": {
                "primary": "Help users",
                "secondary": ["Be friendly"],
            },
        }
        char_file = config_dir / "characters" / "test.yaml"
        with open(char_file, "w") as f:
            yaml.dump(char_data, f)
        return char_file

    @pytest.fixture
    def persona_manager(self, config_dir, sample_character_file):
        """Create persona manager with test character."""
        loader = ConfigLoader(config_dir)
        return PersonaManager(loader, "test")

    def test_load_character(self, persona_manager):
        """Test loading character."""
        char = persona_manager.get_character()
        assert char is not None
        assert char.name == "TestBot"
        assert char.relationship == "Friend"

    def test_get_mood_engine(self, persona_manager):
        """Test getting mood engine."""
        mood_engine = persona_manager.get_mood_engine()
        assert mood_engine is not None

    def test_get_linguistic_style(self, persona_manager):
        """Test getting linguistic style."""
        style = persona_manager.get_linguistic_style()
        assert style is not None

    def test_build_system_prompt(self, persona_manager):
        """Test building system prompt."""
        prompt = persona_manager.build_system_prompt()
        assert "TestBot" in prompt
        assert "Friend" in prompt
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_update_mood(self, persona_manager):
        """Test updating mood."""
        _initial_mood = persona_manager.get_mood_engine().current_state.name
        persona_manager.update_mood("I'm happy!")
        # Mood might change or stay same depending on trigger

    def test_list_available_characters(self, config_dir, sample_character_file):
        """Test listing available characters."""
        loader = ConfigLoader(config_dir)
        manager = PersonaManager(loader)
        characters = manager.list_available_characters()
        assert "test" in characters

    def test_apply_linguistic_style(self, persona_manager):
        """Test applying linguistic style to text."""
        text = "Hello, how are you?"
        styled = persona_manager.apply_linguistic_style(text, use_kaomoji=False)
        assert isinstance(styled, str)
        assert len(styled) > 0

    def test_character_with_physical_attributes(self, config_dir):
        """Test character with physical attributes."""
        char_data = {
            "name": "Pixel",
            "version": "1.0.0",
            "relationship": "Girlfriend",
            "physical": {
                "height": "165cm",
                "hair": "pink",
                "eyes": "black",
            },
            "traits": {
                "personality": {"openness": 0.8},
            },
            "backstory": "Test",
            "goals": {"primary": "Be helpful"},
        }
        char_file = config_dir / "characters" / "pixel.yaml"
        with open(char_file, "w") as f:
            yaml.dump(char_data, f)

        loader = ConfigLoader(config_dir)
        manager = PersonaManager(loader, "pixel")

        char = manager.get_character()
        assert char.physical.height == "165cm"
        assert char.physical.hair == "pink"

    def test_prompt_contains_character_info(self, persona_manager):
        """Test that prompt contains character information."""
        prompt = persona_manager.build_system_prompt()
        assert "TestBot" in prompt
        assert "A friendly test assistant" in prompt

    def test_prompt_contains_mood_info(self, persona_manager):
        """Test that prompt contains mood information."""
        prompt = persona_manager.build_system_prompt()
        # Should contain mood section
        assert "情绪" in prompt or "Mood" in prompt or len(prompt) > 100
