"""Tests for config schemas module."""

import tempfile
from pathlib import Path

import pytest
import yaml

from persona_agent.config.schemas.character import (
    CharacterProfile,
    CommunicationStyle,
    Goals,
    PersonalityTraits,
    PhysicalProfile,
    PsychologicalDriver,
    PsychologicalDrivers,
    Traits,
)
from persona_agent.config.schemas.linguistic import (
    KaomojiCategory,
    LinguisticStyle,
    VerbalTics,
)
from persona_agent.config.schemas.mood import MoodDefinition, MoodState


class TestPhysicalProfile:
    """Tests for PhysicalProfile."""

    def test_default_values(self):
        """Test default physical profile values."""
        profile = PhysicalProfile()

        assert profile.height is None
        assert profile.figure is None
        assert profile.hair is None
        assert profile.eyes is None
        assert profile.attire == {}

    def test_custom_values(self):
        """Test custom physical profile values."""
        profile = PhysicalProfile(
            height="170cm",
            hair="black",
            attire={"top": "shirt", "bottom": "pants"},
        )

        assert profile.height == "170cm"
        assert profile.hair == "black"
        assert profile.attire["top"] == "shirt"


class TestPersonalityTraits:
    """Tests for PersonalityTraits."""

    def test_default_values(self):
        """Test default personality trait values."""
        traits = PersonalityTraits()

        assert traits.openness == 0.5
        assert traits.conscientiousness == 0.5
        assert traits.extraversion == 0.5
        assert traits.agreeableness == 0.5
        assert traits.neuroticism == 0.5

    def test_valid_range(self):
        """Test valid trait range (0.0 - 1.0)."""
        traits = PersonalityTraits(openness=0.8, conscientiousness=0.2, extraversion=1.0)

        assert traits.openness == 0.8
        assert traits.conscientiousness == 0.2
        assert traits.extraversion == 1.0

    def test_invalid_range_too_high(self):
        """Test validation rejects values > 1.0."""
        with pytest.raises(ValueError):
            PersonalityTraits(openness=1.5)

    def test_invalid_range_too_low(self):
        """Test validation rejects values < 0.0."""
        with pytest.raises(ValueError):
            PersonalityTraits(openness=-0.5)


class TestCharacterProfile:
    """Tests for CharacterProfile."""

    def test_basic_profile(self):
        """Test basic character profile creation."""
        profile = CharacterProfile(name="Test Character")

        assert profile.name == "Test Character"
        assert profile.version == "1.0.0"

    def test_from_yaml_file(self, tmp_path):
        """Test loading character from YAML file."""
        yaml_file = tmp_path / "character.yaml"
        content = {
            "name": "YAML Character",
            "version": "1.0.0",
            "backstory": "Test backstory",
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
            "goals": {
                "primary": "Help users",
                "secondary": ["Be friendly", "Be helpful"],
            },
        }
        yaml_file.write_text(yaml.dump(content), encoding="utf-8")

        profile = CharacterProfile.from_yaml(yaml_file)

        assert profile.name == "YAML Character"
        assert profile.traits.personality.openness == 0.8
        assert profile.goals.primary == "Help users"

    def test_from_yaml_legacy_format(self, tmp_path):
        """Test loading character with legacy physical attributes format."""
        yaml_file = tmp_path / "character.yaml"
        content = {
            "name": "Legacy Character",
            "height": "170cm",
            "hair": "black",
            "traits": {"personality": {"openness": 0.8}},
        }
        yaml_file.write_text(yaml.dump(content), encoding="utf-8")

        profile = CharacterProfile.from_yaml(yaml_file)

        assert profile.physical.height == "170cm"
        assert profile.physical.hair == "black"

    def test_from_yaml_file_not_found(self):
        """Test loading from non-existent file."""
        with pytest.raises(FileNotFoundError):
            CharacterProfile.from_yaml(Path("/nonexistent/character.yaml"))

    def test_to_prompt_context(self):
        """Test conversion to prompt context."""
        profile = CharacterProfile(
            name="Test",
            relationship="friend",
            backstory="Test backstory",
            goals=Goals(primary="Help"),
        )

        context = profile.to_prompt_context()

        assert "Test" in context
        assert "friend" in context
        assert "backstory" in context


class TestLinguisticStyle:
    """Tests for LinguisticStyle."""

    def test_default_values(self):
        """Test default linguistic style values."""
        style = LinguisticStyle()

        assert style.nicknames_for_user == []
        assert isinstance(style.verbal_tics, VerbalTics)
        assert style.kaomoji_lexicon == {}

    def test_from_json_file(self, tmp_path):
        """Test loading style from JSON file."""
        json_file = tmp_path / "style.json"
        content = {
            "nicknames_for_user": ["friend", "buddy"],
            "verbal_tics": {
                "triumphant": ["great!"],
                "teasing": ["well..."],
                "shy": ["um..."],
            },
            "kaomoji_lexicon": {"happy": {"category": "happy", "emoticons": ["(^.^)", ":)"]}},
        }
        json_file.write_text(__import__("json").dumps(content), encoding="utf-8")

        style = LinguisticStyle.from_json(json_file)

        assert "friend" in style.nicknames_for_user
        assert "great!" in style.verbal_tics.triumphant
        assert "happy" in style.kaomoji_lexicon

    def test_from_json_legacy_format(self, tmp_path):
        """Test loading style with legacy kaomoji format (list instead of dict)."""
        json_file = tmp_path / "style.json"
        content = {
            "nicknames_for_user": ["friend"],
            "kaomoji_lexicon": {"happy": ["(^.^)", ":)"]},  # Legacy: list
        }
        json_file.write_text(__import__("json").dumps(content), encoding="utf-8")

        style = LinguisticStyle.from_json(json_file)

        assert isinstance(style.kaomoji_lexicon["happy"], KaomojiCategory)
        assert "(^.^)" in style.kaomoji_lexicon["happy"].emoticons

    def test_get_nickname(self):
        """Test getting a random nickname."""
        style = LinguisticStyle(nicknames_for_user=["friend", "buddy"])

        nickname = style.get_nickname()

        assert nickname in ["friend", "buddy"]

    def test_get_nickname_empty(self):
        """Test default nickname when none defined."""
        style = LinguisticStyle()

        nickname = style.get_nickname()

        assert nickname == "你"

    def test_get_kaomoji(self):
        """Test getting a random kaomoji."""
        style = LinguisticStyle(
            kaomoji_lexicon={"happy": KaomojiCategory(category="happy", emoticons=["(^.^)", ":)"])}
        )

        kaomoji = style.get_kaomoji("happy")

        assert kaomoji in ["(^.^)", ":)"]

    def test_get_kaomoji_not_found(self):
        """Test getting kaomoji from non-existent category."""
        style = LinguisticStyle()

        kaomoji = style.get_kaomoji("nonexistent")

        assert kaomoji is None

    def test_get_verbal_tic(self):
        """Test getting verbal tic for mood."""
        style = LinguisticStyle(
            verbal_tics=VerbalTics(
                triumphant=["excellent!"],
                teasing=["well..."],
                shy=["um..."],
            )
        )

        assert style.get_verbal_tic("triumphant") == "excellent!"
        assert style.get_verbal_tic("playful") == "well..."
        assert style.get_verbal_tic("shy") == "um..."

    def test_apply_to_text(self):
        """Test applying style to text."""
        style = LinguisticStyle(
            nicknames_for_user=["friend"],
            kaomoji_lexicon={"default": KaomojiCategory(category="default", emoticons=["(^.^)"])},
        )

        result = style.apply_to_text("Hello", mood="default", use_kaomoji=True)

        assert "Hello" in result
        # Kaomoji may or may not be added depending on random

    def test_apply_to_text_with_nickname(self):
        """Test applying style with nickname replacement."""
        style = LinguisticStyle(nicknames_for_user=["buddy"])

        # Note: nickname replacement is probabilistic (30%)
        # This test may need multiple runs
        result = style.apply_to_text("How are you?", use_nickname=True)

        assert "How are you?" in result


class TestMoodDefinition:
    """Tests for MoodDefinition."""

    def test_basic_mood(self):
        """Test basic mood definition creation."""
        mood = MoodDefinition(
            name="HAPPY",
            display_name="Happy",
            description="Feeling good",
        )

        assert mood.name == "HAPPY"
        assert mood.display_name == "Happy"

    def test_from_markdown_file(self, tmp_path):
        """Test loading moods from markdown file."""
        md_file = tmp_path / "moods.md"
        content = """
## HAPPY: Feeling happy
**触发器:** praise, success
**核心姿态:** positive
**语言风格:** enthusiastic
"""
        md_file.write_text(content, encoding="utf-8")

        moods = MoodDefinition.from_markdown(md_file)

        assert len(moods) == 1
        assert moods[0].name == "HAPPY"
        assert "praise" in moods[0].triggers

    def test_normalize_name(self):
        """Test name normalization."""
        # English names
        assert MoodDefinition._normalize_name("HAPPY") == "HAPPY"
        assert MoodDefinition._normalize_name("MOOD_NAME") == "MOOD_NAME"

        # Chinese names
        assert MoodDefinition._normalize_name("默认") == "DEFAULT"
        assert MoodDefinition._normalize_name("关切") == "CARING"

    def test_to_prompt_modifier(self):
        """Test conversion to prompt modifier."""
        mood = MoodDefinition(
            name="HAPPY",
            display_name="Happy",
            description="Feeling good",
            core_posture="positive",
            language_style="enthusiastic",
            behaviors=["smile", "laugh"],
        )

        modifier = mood.to_prompt_modifier()

        assert "Happy" in modifier
        assert "positive" in modifier
        assert "smile" in modifier


class TestMoodState:
    """Tests for MoodState."""

    def test_default_values(self):
        """Test default mood state values."""
        state = MoodState(name="HAPPY")

        assert state.name == "HAPPY"
        assert state.intensity == 0.5
        assert state.entered_at > 0
        assert state.triggered_by is None

    def test_is_active_no_decay(self):
        """Test is_active without decay."""
        state = MoodState(name="HAPPY")

        assert state.is_active() is True
        assert state.is_active(decay_seconds=None) is True

    def test_is_active_with_decay(self):
        """Test is_active with decay."""
        import time

        state = MoodState(name="HAPPY", entered_at=time.time() - 10)

        assert state.is_active(decay_seconds=60) is True
        assert state.is_active(decay_seconds=5) is False


class TestPsychologicalDrivers:
    """Tests for PsychologicalDrivers."""

    def test_empty_drivers(self):
        """Test drivers with no values."""
        drivers = PsychologicalDrivers()

        assert drivers.drive_for_dominance is None
        assert drivers.drive_for_validation is None
        assert drivers.drive_for_security is None

    def test_with_drivers(self):
        """Test drivers with values."""
        drivers = PsychologicalDrivers(
            drive_for_dominance=PsychologicalDriver(principle="Control the situation")
        )

        assert drivers.drive_for_dominance.principle == "Control the situation"


class TestTraits:
    """Tests for Traits."""

    def test_default_traits(self):
        """Test default traits."""
        traits = Traits()

        assert isinstance(traits.personality, PersonalityTraits)
        assert isinstance(traits.communication_style, CommunicationStyle)

    def test_custom_traits(self):
        """Test custom traits."""
        traits = Traits(
            personality=PersonalityTraits(openness=0.9),
            communication_style=CommunicationStyle(tone="playful"),
        )

        assert traits.personality.openness == 0.9
        assert traits.communication_style.tone == "playful"


class TestGoals:
    """Tests for Goals."""

    def test_primary_goal(self):
        """Test primary goal."""
        goals = Goals(primary="Help users")

        assert goals.primary == "Help users"
        assert goals.secondary == []

    def test_with_secondary_goals(self):
        """Test with secondary goals."""
        goals = Goals(
            primary="Help users",
            secondary=["Be friendly", "Be efficient"],
        )

        assert len(goals.secondary) == 2
        assert "Be friendly" in goals.secondary
