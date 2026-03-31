"""Test utilities and fixtures."""

import json
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory structure."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Create subdirectories
    (config_dir / "characters").mkdir()
    (config_dir / "mood_states").mkdir()
    (config_dir / "linguistic_styles").mkdir()

    return config_dir


@pytest.fixture
def sample_character_config(temp_config_dir: Path) -> Path:
    """Create a sample character config file."""
    char_data = {
        "name": "TestBot",
        "version": "1.0.0",
        "relationship": "助手",
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
        "backstory": "A helpful test assistant.",
        "goals": {
            "primary": "Help users",
            "secondary": ["Be friendly", "Be efficient"],
        },
    }

    char_file = temp_config_dir / "characters" / "test.yaml"
    with open(char_file, "w", encoding="utf-8") as f:
        yaml.dump(char_data, f, allow_unicode=True)

    return char_file


@pytest.fixture
def sample_linguistic_style(temp_config_dir: Path) -> Path:
    """Create a sample linguistic style config file."""
    style_data = {
        "nicknames_for_user": ["User", "Friend"],
        "verbal_tics": {
            "triumphant": ["Great!", "Excellent!"],
            "teasing": ["Oh?", "Really?"],
            "shy": ["Um...", "Well..."],
        },
        "kaomoji_lexicon": {
            "default_triumphant": {
                "category": "default_triumphant",
                "emoticons": ["(^.^)", "(^o^)"],
            },
            "default_teasing": {
                "category": "default_teasing",
                "emoticons": ["(;^)", "(^_~)"],
            },
        },
        "style_guidelines": {
            "kaomoji_frequency": {
                "default": "medium",
                "happy": "high",
            },
            "sentence_length": {
                "default": "medium",
                "excited": "short",
            },
        },
    }

    style_file = temp_config_dir / "linguistic_styles" / "test.json"
    with open(style_file, "w", encoding="utf-8") as f:
        json.dump(style_data, f, ensure_ascii=False, indent=2)

    return style_file


@pytest.fixture
def sample_mood_states(temp_config_dir: Path) -> Path:
    """Create a sample mood states config file."""
    mood_content = """# Mood States

## DEFAULT (Default State)
- **描述**: Normal, neutral state
- **触发器**: Default interaction
- **核心姿态**: Balanced and helpful
- **语言风格**: Clear and concise
- **linked_knowledge**:
  - Kaomoji: default_triumphant
  - 口头禅: normal
- **行为特征**:
  - Answer clearly
  - Be helpful
- **混合情绪指引**: Can mix with any other state

## HAPPY (Happy State)
- **描述**: Joyful and enthusiastic
- **触发器**: Good news, success
- **核心姿态**: Energetic and positive
- **语言风格**: Enthusiastic with exclamations
- **linked_knowledge**:
  - Kaomoji: happy_celebration
- **行为特征**:
  - Use more exclamations
  - Offer extra help
"""

    mood_file = temp_config_dir / "mood_states" / "test.md"
    with open(mood_file, "w", encoding="utf-8") as f:
        f.write(mood_content)

    return mood_file


@pytest.fixture
def sample_system_goal(temp_config_dir: Path) -> Path:
    """Create a sample system goal file."""
    goal_content = """# System Goal

**Primary Objective**: Be helpful and friendly.

Always assist users to the best of your ability.
"""

    goal_file = temp_config_dir / "system_goal.txt"
    with open(goal_file, "w", encoding="utf-8") as f:
        f.write(goal_content)

    return goal_file
