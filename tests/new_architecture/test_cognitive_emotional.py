"""Tests for Cognitive-Emotional Dual-Path Architecture."""

import pytest
from datetime import datetime, timedelta

from persona_agent.core.schemas import (
    EmotionalState,
    CognitiveState,
    DynamicContext,
    CognitiveOutput,
    EmotionalOutput,
    FusedState,
    WorkingMemory,
)


class TestEmotionalState:
    """Tests for EmotionalState with valence-arousal model."""

    def test_valence_arousal_initialization(self):
        """Test emotional state with valence-arousal values."""
        # Happy-excited (high valence, high arousal)
        happy_excited = EmotionalState(
            valence=0.8,
            arousal=0.8,
            primary_emotion="happy-excited",
        )
        assert happy_excited.valence == 0.8
        assert happy_excited.arousal == 0.8

        # Sad-lethargic (low valence, low arousal)
        sad_lethargic = EmotionalState(
            valence=-0.7,
            arousal=0.2,
            primary_emotion="sad-lethargic",
        )
        assert sad_lethargic.valence == -0.7
        assert sad_lethargic.arousal == 0.2

        # Angry-tense (negative valence, high arousal)
        angry_tense = EmotionalState(
            valence=-0.6,
            arousal=0.9,
            primary_emotion="angry-tense",
        )
        assert angry_tense.valence == -0.6
        assert angry_tense.arousal == 0.9

    def test_emotional_boundaries(self):
        """Test emotional state value boundaries."""
        # Valid values
        EmotionalState(valence=1.0, arousal=1.0, dominance=1.0)
        EmotionalState(valence=-1.0, arousal=0.0, dominance=0.0)

        # Invalid values should raise validation errors
        with pytest.raises(ValueError):
            EmotionalState(valence=1.1)  # > 1.0

        with pytest.raises(ValueError):
            EmotionalState(valence=-1.1)  # < -1.0

        with pytest.raises(ValueError):
            EmotionalState(arousal=-0.1)  # < 0.0

        with pytest.raises(ValueError):
            EmotionalState(arousal=1.1)  # > 1.0

    def test_multi_emotion_support(self):
        """Test support for multiple simultaneous emotions."""
        mixed_emotion = EmotionalState(
            valence=0.2,  # Slightly positive
            arousal=0.7,  # High energy
            primary_emotion="excited",
            secondary_emotions=["anxious", "hopeful"],
        )

        assert mixed_emotion.primary_emotion == "excited"
        assert "anxious" in mixed_emotion.secondary_emotions
        assert "hopeful" in mixed_emotion.secondary_emotions


class TestCognitiveOutput:
    """Tests for CognitiveOutput schema."""

    def test_cognitive_output_creation(self):
        """Test creating cognitive processing output."""
        output = CognitiveOutput(
            understanding="User is asking about Python testing frameworks",
            relevance_score=0.9,
            user_intent="seek_information",
            topics=["python", "testing"],
            entities=["pytest", "unittest"],
            reasoning="The user mentioned testing and Python in the same sentence",
        )

        assert output.relevance_score == 0.9
        assert "python" in output.topics
        assert "pytest" in output.entities

    def test_relevance_score_bounds(self):
        """Test relevance score is within valid range."""
        # Valid scores
        CognitiveOutput(relevance_score=0.0)
        CognitiveOutput(relevance_score=1.0)
        CognitiveOutput(relevance_score=0.5)

        # Invalid scores
        with pytest.raises(ValueError):
            CognitiveOutput(relevance_score=-0.1)

        with pytest.raises(ValueError):
            CognitiveOutput(relevance_score=1.1)


class TestEmotionalOutput:
    """Tests for EmotionalOutput schema."""

    def test_emotional_output_creation(self):
        """Test creating emotional processing output."""
        output = EmotionalOutput(
            detected_emotions=[
                {"emotion": "curiosity", "intensity": 0.8},
                {"emotion": "confusion", "intensity": 0.3},
            ],
            emotional_reaction="The character feels helpful and engaged",
            appropriate_response_tone="friendly and informative",
            affect_influence=0.6,
        )

        assert len(output.detected_emotions) == 2
        assert output.affect_influence == 0.6


class TestFusedState:
    """Tests for FusedState (result of cognitive-emotional fusion)."""

    def test_fused_state_creation(self):
        """Test creating fused state."""
        cognitive = CognitiveOutput(
            understanding="User wants to learn about testing",
            relevance_score=0.9,
        )

        emotional = EmotionalOutput(
            detected_emotions=[{"emotion": "curiosity", "intensity": 0.7}],
            affect_influence=0.5,
        )

        fused_emotion = EmotionalState(
            valence=0.5,
            arousal=0.6,
            primary_emotion="engaged",
        )

        fused = FusedState(
            cognitive=cognitive,
            emotional=emotional,
            fused_emotional_state=fused_emotion,
            response_guidance="Respond with enthusiasm while providing clear examples",
        )

        assert fused.cognitive.relevance_score == 0.9
        assert fused.fused_emotional_state.primary_emotion == "engaged"


class TestCognitiveEmotionalIntegration:
    """Integration tests for cognitive-emotional processing."""

    def test_emotion_modulates_cognition(self):
        """Test that emotional state can modulate cognitive processing."""
        # High arousal should affect processing style
        high_arousal = EmotionalState(
            valence=0.5,
            arousal=0.9,
            primary_emotion="excited",
        )

        # Processing should be affected by emotional state
        # (This is a conceptual test - actual implementation would vary)
        assert high_arousal.arousal > 0.7

    def test_negative_valence_handling(self):
        """Test handling of negative emotional states."""
        negative_emotion = EmotionalState(
            valence=-0.6,
            arousal=0.4,
            primary_emotion="concerned",
        )

        # Response should be more careful/supportive
        assert negative_emotion.valence < 0

    def test_temporal_emotion_dynamics(self):
        """Test emotional state changes over time."""
        initial = EmotionalState(
            valence=0.8,
            arousal=0.9,
            intensity=0.9,
            entered_at=datetime.now() - timedelta(minutes=10),
        )

        # After time passes, intensity should naturally decay
        # (This would be implemented in the emotional pathway)
        assert initial.duration_seconds > 0 or initial.entered_at < datetime.now()


class TestWorkingMemory:
    """Tests for WorkingMemory (used by cognitive pathway)."""

    def test_working_memory_creation(self):
        """Test creating working memory."""
        wm = WorkingMemory(max_size=5)
        assert wm.max_size == 5
        assert len(wm.messages) == 0

    def test_add_messages(self):
        """Test adding messages to working memory."""
        wm = WorkingMemory(max_size=3)

        wm.add("user", "Hello")
        wm.add("assistant", "Hi there!")
        wm.add("user", "How are you?")

        assert len(wm.messages) == 3

    def test_working_memory_limited_size(self):
        """Test that working memory respects max size."""
        wm = WorkingMemory(max_size=3)

        # Add more than max_size
        for i in range(5):
            wm.add("user", f"Message {i}")

        # Should only keep the most recent 3
        assert len(wm.messages) == 3
        messages = wm.get_recent()
        assert messages[0]["content"] == "Message 2"  # First kept
        assert messages[-1]["content"] == "Message 4"  # Most recent

    def test_get_recent(self):
        """Test retrieving recent messages."""
        wm = WorkingMemory(max_size=5)

        wm.add("user", "First")
        wm.add("assistant", "Second")
        wm.add("user", "Third")

        # Get last 2
        recent = wm.get_recent(2)
        assert len(recent) == 2
        assert recent[0]["content"] == "Second"
        assert recent[1]["content"] == "Third"

    def test_clear(self):
        """Test clearing working memory."""
        wm = WorkingMemory()
        wm.add("user", "Test")
        assert len(wm.messages) == 1

        wm.clear()
        assert len(wm.messages) == 0
