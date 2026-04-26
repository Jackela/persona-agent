"""Tests for config validator module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from persona_agent.config.validator import ConfigValidator, validate_config


class TestConfigValidator:
    """Tests for ConfigValidator."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create a temporary config directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            (config_dir / "characters").mkdir(parents=True)
            (config_dir / "mood_states").mkdir(parents=True)
            (config_dir / "linguistic_styles").mkdir(parents=True)
            yield config_dir

    @pytest.fixture
    def valid_character_yaml(self, temp_config_dir):
        """Create a valid character YAML file."""
        char_file = temp_config_dir / "characters" / "valid_char.yaml"
        content = """
name: "Valid Character"
version: "1.0.0"
relationship: "friend"
"""
        char_file.write_text(content, encoding="utf-8")
        return char_file

    @pytest.fixture
    def valid_mood_md(self, temp_config_dir):
        """Create a valid mood states markdown file."""
        mood_file = temp_config_dir / "mood_states" / "default.md"
        content = """
## DEFAULT: Default mood
**触发器:** test
**核心姿态:** neutral
**语言风格:** standard
"""
        mood_file.write_text(content, encoding="utf-8")
        return mood_file

    @pytest.fixture
    def valid_style_json(self, temp_config_dir):
        """Create a valid linguistic style JSON file."""
        style_file = temp_config_dir / "linguistic_styles" / "default.json"
        content = """{
    "nicknames_for_user": ["friend"],
    "verbal_tics": {
        "triumphant": ["great!"],
        "teasing": ["well..."],
        "shy": ["um..."]
    },
    "kaomoji_lexicon": {
        "happy": {"category": "happy", "emoticons": ["(^.^)"]}
    }
}"""
        style_file.write_text(content, encoding="utf-8")
        return style_file

    def test_init(self, temp_config_dir):
        """Test validator initialization."""
        validator = ConfigValidator(config_dir=temp_config_dir)

        assert validator.config_dir == temp_config_dir
        assert validator.errors == []
        assert validator.warnings == []

    def test_validate_all_valid(
        self, temp_config_dir, valid_character_yaml, valid_mood_md, valid_style_json
    ):
        """Test validation with all valid configs."""
        validator = ConfigValidator(config_dir=temp_config_dir)

        is_valid = validator.validate_all()

        assert is_valid is True
        assert len(validator.errors) == 0

    def test_validate_missing_directory(self, tmp_path):
        """Test validation with missing required directories."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        # Missing subdirectories

        validator = ConfigValidator(config_dir=config_dir)
        is_valid = validator.validate_all()

        assert is_valid is False
        assert len(validator.errors) > 0
        assert any("characters" in err for err in validator.errors)

    def test_validate_character_without_name(self, temp_config_dir):
        """Test validation catches character without name."""
        char_file = temp_config_dir / "characters" / "invalid_char.yaml"
        char_file.write_text('version: "1.0.0"\n', encoding="utf-8")

        validator = ConfigValidator(config_dir=temp_config_dir)
        is_valid = validator.validate_all()

        assert is_valid is False
        assert any("missing name" in err for err in validator.errors)

    def test_validate_character_without_relationship(self, temp_config_dir):
        """Test validation warns about missing relationship."""
        char_file = temp_config_dir / "characters" / "char_no_rel.yaml"
        char_file.write_text('name: "Test"\nversion: "1.0.0"\n', encoding="utf-8")

        validator = ConfigValidator(config_dir=temp_config_dir)
        validator.validate_all()

        assert any("missing relationship" in warn for warn in validator.warnings)

    def test_validate_invalid_character_yaml(self, temp_config_dir):
        """Test validation catches invalid YAML."""
        char_file = temp_config_dir / "characters" / "invalid.yaml"
        char_file.write_text("invalid yaml content", encoding="utf-8")

        validator = ConfigValidator(config_dir=temp_config_dir)
        is_valid = validator.validate_all()

        assert is_valid is False

    def test_validate_mood_duplicate_names(self, temp_config_dir):
        """Test validation catches duplicate mood names."""
        mood_file = temp_config_dir / "mood_states" / "dup_moods.md"
        content = """
## MOOD1: First mood
**触发器:** test

## MOOD1: Duplicate mood
**触发器:** test2
"""
        mood_file.write_text(content, encoding="utf-8")

        validator = ConfigValidator(config_dir=temp_config_dir)
        is_valid = validator.validate_all()

        assert is_valid is False
        assert any("duplicate mood" in err for err in validator.errors)

    def test_validate_mood_no_definitions(self, temp_config_dir):
        """Test validation warns about no mood definitions."""
        mood_file = temp_config_dir / "mood_states" / "empty.md"
        mood_file.write_text("\n", encoding="utf-8")

        validator = ConfigValidator(config_dir=temp_config_dir)
        validator.validate_all()

        # Should have warning about no mood definitions
        assert any("no mood definitions" in warn for warn in validator.warnings)

    def test_validate_style_without_nicknames(self, temp_config_dir, valid_mood_md):
        """Test validation warns about style without nicknames."""
        style_file = temp_config_dir / "linguistic_styles" / "no_nick.json"
        content = """{
    "verbal_tics": {"triumphant": ["great!"]},
    "kaomoji_lexicon": {"happy": {"category": "happy", "emoticons": [":)"]}}
}"""
        style_file.write_text(content, encoding="utf-8")

        validator = ConfigValidator(config_dir=temp_config_dir)
        validator.validate_all()

        assert any("no nicknames" in warn for warn in validator.warnings)

    def test_validate_style_without_kaomoji(self, temp_config_dir, valid_mood_md):
        """Test validation warns about style without kaomoji."""
        style_file = temp_config_dir / "linguistic_styles" / "no_kao.json"
        content = """{
    "nicknames_for_user": ["friend"],
    "verbal_tics": {"triumphant": ["great!"]}
}"""
        style_file.write_text(content, encoding="utf-8")

        validator = ConfigValidator(config_dir=temp_config_dir)
        validator.validate_all()

        assert any("no kaomoji" in warn for warn in validator.warnings)

    def test_validate_invalid_style_json(self, temp_config_dir):
        """Test validation catches invalid JSON."""
        style_file = temp_config_dir / "linguistic_styles" / "invalid.json"
        style_file.write_text('{"invalid json', encoding="utf-8")

        validator = ConfigValidator(config_dir=temp_config_dir)
        is_valid = validator.validate_all()

        assert is_valid is False

    def test_get_report_valid(self, temp_config_dir, valid_character_yaml):
        """Test getting validation report for valid config."""
        validator = ConfigValidator(config_dir=temp_config_dir)
        validator.validate_all()

        report = validator.get_report()

        assert report["valid"] is True
        assert report["error_count"] == 0
        assert "errors" in report
        assert "warnings" in report

    def test_get_report_invalid(self, temp_config_dir):
        """Test getting validation report for invalid config."""
        # Create invalid character
        char_file = temp_config_dir / "characters" / "invalid.yaml"
        char_file.write_text("not a valid structure", encoding="utf-8")

        validator = ConfigValidator(config_dir=temp_config_dir)
        validator.validate_all()

        report = validator.get_report()

        assert report["valid"] is False
        assert report["error_count"] > 0

    def test_get_report_with_warnings(self, temp_config_dir, valid_character_yaml, valid_mood_md):
        """Test getting report with warnings."""
        # Create style without nicknames
        style_file = temp_config_dir / "linguistic_styles" / "warn.json"
        style_file.write_text('{"kaomoji_lexicon": {}}', encoding="utf-8")

        validator = ConfigValidator(config_dir=temp_config_dir)
        validator.validate_all()

        report = validator.get_report()

        assert report["valid"] is True
        assert report["warning_count"] > 0

    def test_print_report_valid(self, temp_config_dir, valid_character_yaml):
        """Test printing valid report."""
        validator = ConfigValidator(config_dir=temp_config_dir)
        validator.validate_all()

        # Should not raise
        validator.print_report()

    def test_print_report_invalid(self, temp_config_dir):
        """Test printing invalid report."""
        validator = ConfigValidator(config_dir=temp_config_dir)
        validator.validate_all()

        # Should not raise even with errors
        validator.print_report()


class TestValidateConfig:
    """Tests for validate_config convenience function."""

    def test_validate_config_valid(self, tmp_path):
        """Test validate_config with valid directory."""
        config_dir = tmp_path / "config"
        (config_dir / "characters").mkdir(parents=True)
        (config_dir / "mood_states").mkdir()
        (config_dir / "linguistic_styles").mkdir()

        with patch("persona_agent.config.validator.ConfigValidator.print_report"):
            result = validate_config(config_dir)

        assert result is True

    def test_validate_config_invalid(self, tmp_path):
        """Test validate_config with invalid directory."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        with patch("persona_agent.config.validator.ConfigValidator.print_report"):
            result = validate_config(config_dir)

        assert result is False


class TestConfigValidatorEdgeCases:
    """Edge case tests for ConfigValidator."""

    def test_validate_empty_directories(self, temp_config_dir):
        """Test validation with empty directories."""
        validator = ConfigValidator(config_dir=temp_config_dir)
        is_valid = validator.validate_all()

        # Should be valid (no errors, but may have warnings)
        assert isinstance(is_valid, bool)

    def test_validate_nonexistent_character_dir(self, temp_config_dir):
        """Test validation when characters directory doesn't exist."""
        import shutil

        shutil.rmtree(temp_config_dir / "characters")

        validator = ConfigValidator(config_dir=temp_config_dir)
        is_valid = validator.validate_all()

        assert is_valid is False

    def test_validate_character_yaml_and_yml(self, temp_config_dir):
        """Test validation with both .yaml and .yml files."""
        yaml_file = temp_config_dir / "characters" / "char1.yaml"
        yaml_file.write_text('name: "Char1"', encoding="utf-8")

        yml_file = temp_config_dir / "characters" / "char2.yml"
        yml_file.write_text('name: "Char2"', encoding="utf-8")

        validator = ConfigValidator(config_dir=temp_config_dir)
        is_valid = validator.validate_all()

        # Both should be validated
        assert isinstance(is_valid, bool)
