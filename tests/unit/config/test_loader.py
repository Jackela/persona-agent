"""Tests for config loader module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from persona_agent.config.loader import ConfigLoader


class TestConfigLoader:
    """Tests for ConfigLoader."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create a temporary config directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            # Create required subdirectories
            (config_dir / "characters").mkdir(parents=True)
            (config_dir / "mood_states").mkdir(parents=True)
            (config_dir / "linguistic_styles").mkdir(parents=True)
            yield config_dir

    @pytest.fixture
    def sample_character_yaml(self, temp_config_dir):
        """Create a sample character YAML file."""
        char_file = temp_config_dir / "characters" / "test_char.yaml"
        content = """
name: "Test Character"
version: "1.0.0"
relationship: "friend"
backstory: "A test character"
goals:
  primary: "Help with testing"
"""
        char_file.write_text(content, encoding="utf-8")
        return char_file

    @pytest.fixture
    def sample_mood_md(self, temp_config_dir):
        """Create a sample mood states markdown file."""
        mood_file = temp_config_dir / "mood_states" / "default.md"
        content = """
## DEFAULT: Default mood
**触发器:** test trigger
**核心姿态:** neutral
**语言风格:** standard
"""
        mood_file.write_text(content, encoding="utf-8")
        return mood_file

    @pytest.fixture
    def sample_style_json(self, temp_config_dir):
        """Create a sample linguistic style JSON file."""
        style_file = temp_config_dir / "linguistic_styles" / "default.json"
        content = """{
    "nicknames_for_user": ["friend"],
    "verbal_tics": {
        "triumphant": ["great!"],
        "teasing": ["well..."],
        "shy": ["um..."]
    },
    "kaomoji_lexicon": {
        "happy": {
            "category": "happy",
            "emoticons": ["(^.^)"]
        }
    }
}"""
        style_file.write_text(content, encoding="utf-8")
        return style_file

    def test_init_with_default_config_dir(self):
        """Test initialization with default config directory search."""
        with patch.object(Path, "exists") as mock_exists:
            mock_exists.side_effect = [True, False]  # local exists, user doesn't
            with patch.object(Path, "mkdir"):
                loader = ConfigLoader()
                assert loader.config_dir is not None

    def test_init_with_explicit_config_dir(self, temp_config_dir):
        """Test initialization with explicit config directory."""
        loader = ConfigLoader(config_dir=temp_config_dir)

        assert loader.config_dir == temp_config_dir

    def test_load_character_success(self, temp_config_dir, sample_character_yaml):
        """Test successful character loading."""
        loader = ConfigLoader(config_dir=temp_config_dir)

        profile = loader.load_character("test_char")

        assert profile.name == "Test Character"
        assert profile.version == "1.0.0"
        assert profile.relationship == "friend"

    def test_load_character_from_cache(self, temp_config_dir, sample_character_yaml):
        """Test character caching."""
        loader = ConfigLoader(config_dir=temp_config_dir)

        # Load first time
        profile1 = loader.load_character("test_char")
        # Load from cache
        profile2 = loader.load_character("test_char")

        assert profile1 is profile2

    def test_load_character_not_found(self, temp_config_dir):
        """Test loading non-existent character."""
        loader = ConfigLoader(config_dir=temp_config_dir)

        with pytest.raises(FileNotFoundError):
            loader.load_character("nonexistent")

    def test_load_character_with_yml_extension(self, temp_config_dir):
        """Test loading character with .yml extension."""
        char_file = temp_config_dir / "characters" / "test_char.yml"
        char_file.write_text('name: "YML Character"', encoding="utf-8")

        loader = ConfigLoader(config_dir=temp_config_dir)
        profile = loader.load_character("test_char")

        assert profile.name == "YML Character"

    def test_load_linguistic_style_success(self, temp_config_dir, sample_style_json):
        """Test successful linguistic style loading."""
        loader = ConfigLoader(config_dir=temp_config_dir)

        style = loader.load_linguistic_style("default")

        assert "friend" in style.nicknames_for_user
        assert "happy" in style.kaomoji_lexicon

    def test_load_linguistic_style_from_cache(self, temp_config_dir, sample_style_json):
        """Test linguistic style caching."""
        loader = ConfigLoader(config_dir=temp_config_dir)

        style1 = loader.load_linguistic_style("default")
        style2 = loader.load_linguistic_style("default")

        assert style1 is style2

    def test_load_linguistic_style_not_found(self, temp_config_dir):
        """Test loading non-existent style."""
        loader = ConfigLoader(config_dir=temp_config_dir)

        with pytest.raises(FileNotFoundError):
            loader.load_linguistic_style("nonexistent")

    def test_load_mood_states_success(self, temp_config_dir, sample_mood_md):
        """Test successful mood states loading."""
        loader = ConfigLoader(config_dir=temp_config_dir)

        moods = loader.load_mood_states("default")

        assert len(moods) > 0
        assert moods[0].name == "DEFAULT"

    def test_load_mood_states_from_cache(self, temp_config_dir, sample_mood_md):
        """Test mood states caching."""
        loader = ConfigLoader(config_dir=temp_config_dir)

        moods1 = loader.load_mood_states("default")
        moods2 = loader.load_mood_states("default")

        assert moods1 is moods2

    def test_load_mood_states_not_found(self, temp_config_dir):
        """Test loading non-existent mood states."""
        loader = ConfigLoader(config_dir=temp_config_dir)

        with pytest.raises(FileNotFoundError):
            loader.load_mood_states("nonexistent")

    def test_load_system_goal(self, temp_config_dir):
        """Test loading system goal."""
        goal_file = temp_config_dir / "system_goal.txt"
        goal_file.write_text("You are a helpful assistant.", encoding="utf-8")

        loader = ConfigLoader(config_dir=temp_config_dir)
        goal = loader.load_system_goal()

        assert "helpful assistant" in goal

    def test_load_system_goal_not_found(self, temp_config_dir):
        """Test loading non-existent system goal."""
        loader = ConfigLoader(config_dir=temp_config_dir)

        with pytest.raises(FileNotFoundError):
            loader.load_system_goal()

    def test_list_characters(self, temp_config_dir, sample_character_yaml):
        """Test listing characters."""
        loader = ConfigLoader(config_dir=temp_config_dir)

        characters = loader.list_characters()

        assert "test_char" in characters

    def test_list_linguistic_styles(self, temp_config_dir, sample_style_json):
        """Test listing linguistic styles."""
        loader = ConfigLoader(config_dir=temp_config_dir)

        styles = loader.list_linguistic_styles()

        assert "default" in styles

    def test_list_mood_states(self, temp_config_dir, sample_mood_md):
        """Test listing mood states."""
        loader = ConfigLoader(config_dir=temp_config_dir)

        moods = loader.list_mood_states()

        assert "default" in moods

    def test_clear_cache(self, temp_config_dir, sample_character_yaml, sample_style_json):
        """Test clearing cache."""
        loader = ConfigLoader(config_dir=temp_config_dir)

        # Load and cache
        loader.load_character("test_char")
        loader.load_linguistic_style("default")

        # Clear cache
        loader.clear_cache()

        # Verify cache is cleared
        assert len(loader._character_cache) == 0
        assert len(loader._style_cache) == 0


class TestConfigLoaderFindConfigDir:
    """Tests for config directory discovery."""

    def test_find_local_config(self, tmp_path):
        """Test finding local config directory."""
        local_config = tmp_path / "config"
        local_config.mkdir()

        with patch.object(Path, "cwd", return_value=tmp_path):
            loader = ConfigLoader()
            assert loader.config_dir == local_config

    def test_find_user_config(self, tmp_path):
        """Test falling back to user config."""
        user_config = tmp_path / ".config" / "persona-agent"
        user_config.mkdir(parents=True)

        with (
            patch.object(Path, "cwd", return_value=tmp_path / "nowhere"),
            patch.object(Path, "home", return_value=tmp_path),
        ):
            loader = ConfigLoader()
            assert loader.config_dir == user_config

    def test_create_user_config(self, tmp_path):
        """Test creating user config if neither exists."""
        user_config = tmp_path / ".config" / "persona-agent"

        with (
            patch.object(Path, "cwd", return_value=tmp_path / "nowhere"),
            patch.object(Path, "home", return_value=tmp_path),
        ):
            _ = ConfigLoader()
            assert user_config.exists()
