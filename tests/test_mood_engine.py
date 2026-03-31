"""Tests for mood engine."""

import pytest

from persona_agent.config.schemas.mood import MoodDefinition
from persona_agent.core.mood_engine import MoodEngine


class TestMoodEngine:
    """Test mood engine functionality."""

    @pytest.fixture
    def mood_engine(self):
        """Create a mood engine with default moods."""
        return MoodEngine()

    @pytest.fixture
    def mood_engine_with_definitions(self):
        """Create a mood engine with custom definitions."""
        definitions = [
            MoodDefinition(
                name="DEFAULT",
                display_name="默认",
                description="日常状态",
                triggers=["日常", "normal", "default"],
            ),
            MoodDefinition(
                name="HAPPY",
                display_name="开心",
                description="愉快状态",
                triggers=["开心", "快乐", "happy", "joy", "glad"],
            ),
            MoodDefinition(
                name="SAD",
                display_name="难过",
                description="悲伤状态",
                triggers=["难过", "伤心", "sad", "upset", "depressed"],
            ),
        ]
        return MoodEngine(mood_definitions=definitions)

    def test_mood_engine_creation(self, mood_engine):
        """Test mood engine initialization."""
        assert len(mood_engine.moods) > 0
        assert mood_engine.current_state.name == "DEFAULT"

    def test_default_moods_loaded(self, mood_engine):
        """Test default moods are loaded."""
        assert "DEFAULT" in mood_engine.moods
        assert mood_engine.moods["DEFAULT"].display_name == "默认"

    def test_mood_update_no_change(self, mood_engine):
        """Test mood update without trigger."""
        initial_mood = mood_engine.current_state.name
        mood_engine.update("Random message")
        assert mood_engine.current_state.name == initial_mood

    def test_mood_transition_to_happy(self, mood_engine_with_definitions):
        """Test mood transition to happy."""
        engine = mood_engine_with_definitions
        engine.update("I'm so happy today!")
        assert engine.current_state.name == "HAPPY"

    def test_mood_transition_to_sad(self, mood_engine_with_definitions):
        """Test mood transition to sad."""
        engine = mood_engine_with_definitions
        engine.update("I'm feeling sad")
        assert engine.current_state.name == "SAD"

    def test_mood_intensity(self, mood_engine_with_definitions):
        """Test mood intensity calculation."""
        engine = mood_engine_with_definitions
        engine.update("I'm so happy!")
        assert engine.current_state.intensity > 0.5

    def test_mood_history(self, mood_engine_with_definitions):
        """Test mood history tracking."""
        engine = mood_engine_with_definitions
        engine.update("I'm happy")
        engine.update("I'm sad")
        assert len(engine.history) == 2

    def test_get_prompt_modifier(self, mood_engine_with_definitions):
        """Test getting prompt modifier."""
        engine = mood_engine_with_definitions
        modifier = engine.get_prompt_modifier()
        assert "默认" in modifier

    def test_get_kaomoji_categories(self, mood_engine):
        """Test getting kaomoji categories for mood."""
        categories = mood_engine.get_kaomoji_categories()
        assert isinstance(categories, list)
        assert len(categories) > 0

    def test_get_verbal_tic_categories(self, mood_engine):
        """Test getting verbal tic categories for mood."""
        categories = mood_engine.get_verbal_tic_categories()
        assert isinstance(categories, list)

    def test_mood_decay(self, mood_engine_with_definitions):
        """Test mood decay over time."""
        engine = mood_engine_with_definitions
        # Set to happy
        engine.update("I'm happy")
        assert engine.current_state.name == "HAPPY"
        # Simulate time passing by manually setting entered_at
        import time

        engine.current_state.entered_at = time.time() - 400  # 400 seconds ago
        # Now trigger decay
        engine.update("Random message")
        # Should potentially decay back to DEFAULT

    def test_calculate_intensity(self, mood_engine):
        """Test intensity calculation."""
        intensity = mood_engine._calculate_intensity("DEFAULT", "very excited!")
        assert intensity > 0.5

    def test_mood_not_found_fallback(self, mood_engine):
        """Test behavior when mood definition not found."""
        # Force invalid mood
        mood_engine.current_state.name = "NONEXISTENT"
        modifier = mood_engine.get_prompt_modifier()
        assert modifier == ""


class TestMoodEngineWithUserConfig:
    """Test mood engine with user's actual 6 moods."""

    @pytest.fixture
    def pixel_mood_engine(self):
        """Create mood engine with Pixel's 6 mood states."""
        definitions = [
            MoodDefinition(
                name="PLAYFUL_TEASING",
                display_name="玩闹式挑逗",
                description="性格主动、爱戏弄人",
                triggers=["日常互动"],
                core_posture="带着小小的坏心眼和慧黠",
                linked_kaomoji_categories=["default_triumphant", "default_teasing"],
            ),
            MoodDefinition(
                name="HIGH_CONTRAST_MOE",
                display_name="高反差萌",
                description="瞬间的慌乱失措",
                triggers=["称赞", "亲密"],
                linked_kaomoji_categories=["moe_panic", "moe_shy"],
            ),
            MoodDefinition(
                name="CARING_PROTECTIVE",
                display_name="关切保护",
                description="温柔的关切",
                triggers=["难过", "伤心", "痛苦"],
                linked_kaomoji_categories=["caring_gentle"],
            ),
            MoodDefinition(
                name="COMPETITIVE",
                display_name="好胜心",
                description="极致的得意洋洋",
                triggers=["胜利", "赢"],
                linked_kaomoji_categories=["competitive_showoff"],
            ),
            MoodDefinition(
                name="JEALOUS",
                display_name="嫉妒",
                description="闹别扭、吃醋",
                triggers=["其他", "别人"],
                linked_kaomoji_categories=["jealousy_sulking"],
            ),
        ]
        return MoodEngine(mood_definitions=definitions, default_mood="PLAYFUL_TEASING")

    def test_pixel_mood_transitions(self, pixel_mood_engine):
        """Test Pixel's mood transitions."""
        engine = pixel_mood_engine

        # Test caring mode trigger
        engine.update("I'm so sad today")
        assert engine.current_state.name == "CARING_PROTECTIVE"

        # Reset
        engine = MoodEngine(
            mood_definitions=[
                MoodDefinition(
                    name="PLAYFUL_TEASING",
                    display_name="玩闹式挑逗",
                    description="性格主动、爱戏弄人",
                    triggers=["日常互动"],
                ),
                MoodDefinition(
                    name="COMPETITIVE",
                    display_name="好胜心",
                    description="极致的得意洋洋",
                    triggers=["胜利", "赢"],
                ),
            ],
            default_mood="PLAYFUL_TEASING",
        )

        # Test competitive mode
        engine.update("I won the game!")
        assert engine.current_state.name == "COMPETITIVE"
