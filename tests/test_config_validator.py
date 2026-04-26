"""Tests for configuration validator."""

import tempfile
from pathlib import Path

import pytest

from persona_agent.config.validator import ConfigValidator, validate_config


class TestConfigValidator:
    """Test configuration validation."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary config directory structure."""
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp) / "config"

            # Create required directories
            (config_dir / "characters").mkdir(parents=True)
            (config_dir / "mood_states").mkdir(parents=True)
            (config_dir / "linguistic_styles").mkdir(parents=True)

            yield config_dir

    def test_valid_empty_config(self, temp_config_dir):
        """Test validating empty but valid config structure."""
        validator = ConfigValidator(temp_config_dir)
        is_valid = validator.validate_all()

        assert is_valid is True
        assert len(validator.errors) == 0

    def test_missing_directory(self, temp_config_dir):
        """Test validation with missing directory."""
        # Remove one directory
        import shutil

        shutil.rmtree(temp_config_dir / "characters")

        validator = ConfigValidator(temp_config_dir)
        is_valid = validator.validate_all()

        assert is_valid is False
        assert any("characters" in e for e in validator.errors)

    def test_valid_character(self, temp_config_dir):
        """Test validating a valid character file."""
        char_file = temp_config_dir / "characters" / "test.yaml"
        char_file.write_text("""
name: "Test Character"
version: "1.0.0"
relationship: "friend"
traits:
  personality:
    openness: 0.8
    conscientiousness: 0.7
    extraversion: 0.6
    agreeableness: 0.9
    neuroticism: 0.2
backstory: "A test character"
goals:
  primary: "Help users"
""")

        validator = ConfigValidator(temp_config_dir)
        is_valid = validator.validate_all()

        assert is_valid is True

    def test_character_missing_name(self, temp_config_dir):
        """Test character validation with missing name."""
        char_file = temp_config_dir / "characters" / "invalid.yaml"
        char_file.write_text("""
version: "1.0.0"
relationship: "friend"
""")

        validator = ConfigValidator(temp_config_dir)
        is_valid = validator.validate_all()

        # Missing name should cause validation error
        assert is_valid is False
        assert any("name" in e.lower() for e in validator.errors)

    def test_valid_linguistic_style(self, temp_config_dir):
        """Test validating linguistic style."""
        style_file = temp_config_dir / "linguistic_styles" / "test.json"
        style_file.write_text("""
{
    "nicknames_for_user": ["friend", "buddy"],
    "verbal_tics": {
        "triumphant": ["great!"],
        "teasing": ["oh?"],
        "shy": ["um..."]
    },
    "kaomoji_lexicon": {
        "happy": {
            "category": "happy",
            "emoticons": [":)", ":D"]
        }
    }
}
""")

        validator = ConfigValidator(temp_config_dir)
        is_valid = validator.validate_all()

        assert is_valid is True
        # Should have no warnings since we have nicknames and kaomoji
        assert len(validator.warnings) == 0

    def test_linguistic_style_missing_nicknames(self, temp_config_dir):
        """Test style validation with missing nicknames."""
        style_file = temp_config_dir / "linguistic_styles" / "test.json"
        style_file.write_text("""
{
    "nicknames_for_user": [],
    "verbal_tics": {},
    "kaomoji_lexicon": {}
}
""")

        validator = ConfigValidator(temp_config_dir)
        is_valid = validator.validate_all()

        assert is_valid is True  # Warnings don't make it invalid
        assert any("nicknames" in w for w in validator.warnings)

    def test_get_report(self, temp_config_dir):
        """Test getting validation report."""
        validator = ConfigValidator(temp_config_dir)
        validator.validate_all()

        report = validator.get_report()

        assert "valid" in report
        assert "errors" in report
        assert "warnings" in report
        assert "error_count" in report
        assert "warning_count" in report

    def test_report_with_errors_and_warnings(self, temp_config_dir):
        """Test report generation with issues."""
        # Create invalid character
        char_file = temp_config_dir / "characters" / "test.yaml"
        char_file.write_text("invalid yaml content")

        validator = ConfigValidator(temp_config_dir)
        validator.validate_all()

        report = validator.get_report()

        assert report["valid"] is False
        assert report["error_count"] > 0


class TestValidateConfigFunction:
    """Test the validate_config convenience function."""

    def test_validate_config_valid(self, capsys):
        """Test validating a valid config."""
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp) / "config"
            (config_dir / "characters").mkdir(parents=True)
            (config_dir / "mood_states").mkdir(parents=True)
            (config_dir / "linguistic_styles").mkdir(parents=True)

            result = validate_config(config_dir)

            assert result is True
