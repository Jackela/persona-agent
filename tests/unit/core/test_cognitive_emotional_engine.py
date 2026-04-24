"""Tests for cognitive_emotional_engine module."""

import json
import math
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from persona_agent.core.cognitive_emotional_engine import (
    EMOTION_VAD_MAP,
    TONE_MAPPINGS,
    CognitiveEmotionalEngine,
    CognitivePathway,
    EmotionalPathway,
    FusionLayer,
    create_neutral_emotional_state,
    determine_response_tone,
    emotional_distance,
    emotional_similarity,
    interpolate_vad,
    vad_to_emotion_label,
)
from persona_agent.core.schemas import (
    CognitiveOutput,
    EmotionalOutput,
    EmotionalState,
    FusedState,
    WorkingMemory,
)


# ============================================================================
# Pure Function Tests
# ============================================================================


class TestVadToEmotionLabel:
    """Tests for vad_to_emotion_label."""

    def test_exact_match(self):
        """Test exact VAD match returns correct emotion."""
        v, a, d = EMOTION_VAD_MAP["happy"]
        assert vad_to_emotion_label(v, a, d) == "happy"

    def test_nearest_match(self):
        """Test nearest emotion is returned for non-exact VAD."""
        # Close to happy but slightly different
        result = vad_to_emotion_label(0.75, 0.55, 0.55)
        assert result == "happy"

    def test_unknown_vad_defaults_to_neutral(self):
        """Test that unknown VAD defaults to nearest, which may be neutral."""
        result = vad_to_emotion_label(0.0, 0.5, 0.5)
        assert result == "neutral"

    def test_extreme_values(self):
        """Test extreme VAD values."""
        result = vad_to_emotion_label(-1.0, 1.0, 0.0)
        assert result == "scared"

    def test_all_emotions_have_valid_vad(self):
        """Test that all emotions in EMOTION_VAD_MAP have valid coordinates."""
        for emotion, (v, a, d) in EMOTION_VAD_MAP.items():
            assert -1.0 <= v <= 1.0, f"{emotion} valence out of range"
            assert 0.0 <= a <= 1.0, f"{emotion} arousal out of range"
            assert 0.0 <= d <= 1.0, f"{emotion} dominance out of range"


class TestInterpolateVad:
    """Tests for interpolate_vad."""

    def test_single_emotion(self):
        """Test interpolation with single emotion."""
        emotions = [{"label": "happy", "intensity": 0.8}]
        v, a, d, secondary = interpolate_vad(emotions)
        e_v, e_a, e_d = EMOTION_VAD_MAP["happy"]
        assert v == pytest.approx(e_v, abs=0.01)
        assert a == pytest.approx(e_a, abs=0.01)
        assert d == pytest.approx(e_d, abs=0.01)
        assert secondary == []

    def test_multiple_emotions(self):
        """Test interpolation with multiple emotions."""
        emotions = [
            {"label": "happy", "intensity": 0.8},
            {"label": "sad", "intensity": 0.4},
        ]
        v, a, d, secondary = interpolate_vad(emotions)
        # Should be weighted toward happy (higher intensity)
        assert v > 0.0  # happy has positive valence, sad negative
        assert 0.0 <= a <= 1.0
        assert 0.0 <= d <= 1.0
        # sad has intensity 0.4 which is < 0.6 and > 0.2, so it's secondary
        assert "sad" in secondary

    def test_empty_emotions(self):
        """Test empty emotions list returns neutral."""
        v, a, d, secondary = interpolate_vad([])
        assert v == 0.0
        assert a == 0.5
        assert d == 0.5
        assert secondary == []

    def test_zero_total_weight(self):
        """Test when all emotions have zero intensity."""
        emotions = [
            {"label": "happy", "intensity": 0.0},
            {"label": "sad", "intensity": 0.0},
        ]
        v, a, d, secondary = interpolate_vad(emotions)
        assert v == 0.0
        assert a == 0.5
        assert d == 0.5
        assert secondary == []

    def test_custom_vad_values(self):
        """Test emotions with custom VAD values not in map."""
        emotions = [
            {
                "label": "custom_emotion",
                "intensity": 1.0,
                "valence": 0.5,
                "arousal": 0.7,
                "dominance": 0.3,
            }
        ]
        v, a, d, secondary = interpolate_vad(emotions)
        assert v == pytest.approx(0.5, abs=0.01)
        assert a == pytest.approx(0.7, abs=0.01)
        assert d == pytest.approx(0.3, abs=0.01)

    def test_clamping(self):
        """Test that values are clamped to valid ranges."""
        emotions = [
            {
                "label": "custom",
                "intensity": 1.0,
                "valence": 2.0,  # Should be clamped to 1.0
                "arousal": -0.5,  # Should be clamped to 0.0
                "dominance": 1.5,  # Should be clamped to 1.0
            }
        ]
        v, a, d, _ = interpolate_vad(emotions)
        assert v == 1.0
        assert a == 0.0
        assert d == 1.0

    def test_secondary_emotions_filtering(self):
        """Test secondary emotions are correctly filtered."""
        emotions = [
            {"label": "happy", "intensity": 0.9},  # Not secondary (>= 0.6)
            {"label": "sad", "intensity": 0.5},  # Secondary (0.2 < intensity < 0.6)
            {"label": "angry", "intensity": 0.1},  # Not secondary (<= 0.2)
        ]
        _, _, _, secondary = interpolate_vad(emotions)
        assert "sad" in secondary
        assert "happy" not in secondary
        assert "angry" not in secondary


class TestDetermineResponseTone:
    """Tests for determine_response_tone."""

    def test_enthusiastic_tone(self):
        """Test enthusiastic tone detection."""
        tone = determine_response_tone(0.8, 0.8, 0.6)
        assert tone == "enthusiastic"

    def test_warm_tone(self):
        """Test warm tone detection."""
        tone = determine_response_tone(0.6, 0.4, 0.5)
        assert tone == "warm"

    def test_somber_tone(self):
        """Test somber tone detection."""
        tone = determine_response_tone(-0.6, 0.4, 0.3)
        assert tone == "somber"

    def test_neutral_fallback(self):
        """Test neutral fallback for unmatched VAD."""
        tone = determine_response_tone(-10.0, -10.0, -10.0)
        assert tone == "neutral"

    def test_all_tone_mappings(self):
        """Test that all tone mappings produce valid tones."""
        for (t_v, t_a, t_d), expected_tone in TONE_MAPPINGS:
            tone = determine_response_tone(t_v, t_a, t_d)
            if expected_tone == "concerned":
                assert tone in ("somber", "concerned")
            elif expected_tone == "confident":
                assert tone in ("warm", "confident")
            elif expected_tone == "neutral":
                assert tone in ("somber", "neutral")
            else:
                assert tone == expected_tone


class TestCreateNeutralEmotionalState:
    """Tests for create_neutral_emotional_state."""

    def test_default_values(self):
        """Test default neutral state values."""
        state = create_neutral_emotional_state()
        assert state.valence == 0.0
        assert state.arousal == 0.5
        assert state.dominance == 0.5
        assert state.primary_emotion == "neutral"
        assert state.secondary_emotions == []
        assert state.intensity == 0.3

    def test_is_emotional_state_instance(self):
        """Test that returned value is EmotionalState instance."""
        state = create_neutral_emotional_state()
        assert isinstance(state, EmotionalState)


class TestEmotionalDistance:
    """Tests for emotional_distance."""

    def test_identical_states(self):
        """Test distance between identical states is zero."""
        state = create_neutral_emotional_state()
        assert emotional_distance(state, state) == 0.0

    def test_different_states(self):
        """Test distance between different states."""
        state1 = create_neutral_emotional_state()
        state2 = EmotionalState(
            valence=1.0,
            arousal=1.0,
            dominance=1.0,
            primary_emotion="happy",
        )
        distance = emotional_distance(state1, state2)
        expected = math.sqrt((0.0 - 1.0) ** 2 + (0.5 - 1.0) ** 2 + (0.5 - 1.0) ** 2)
        assert distance == pytest.approx(expected, abs=0.01)

    def test_symmetry(self):
        """Test distance is symmetric."""
        state1 = EmotionalState(valence=-1.0, arousal=0.0, dominance=0.0, primary_emotion="sad")
        state2 = EmotionalState(valence=1.0, arousal=1.0, dominance=1.0, primary_emotion="happy")
        assert emotional_distance(state1, state2) == emotional_distance(state2, state1)


class TestEmotionalSimilarity:
    """Tests for emotional_similarity."""

    def test_identical_states(self):
        """Test similarity between identical states is 1.0."""
        state = create_neutral_emotional_state()
        assert emotional_similarity(state, state) == 1.0

    def test_different_states(self):
        """Test similarity between different states."""
        state1 = create_neutral_emotional_state()
        state2 = EmotionalState(
            valence=1.0,
            arousal=1.0,
            dominance=1.0,
            primary_emotion="happy",
        )
        similarity = emotional_similarity(state1, state2)
        assert 0.0 <= similarity < 1.0

    def test_maximally_different(self):
        """Test similarity for maximally different states."""
        state1 = EmotionalState(valence=-1.0, arousal=0.0, dominance=0.0, primary_emotion="sad")
        state2 = EmotionalState(valence=1.0, arousal=1.0, dominance=1.0, primary_emotion="happy")
        similarity = emotional_similarity(state1, state2)
        assert similarity >= 0.0
        assert similarity < 0.5  # Should be quite low

    def test_symmetry(self):
        """Test similarity is symmetric."""
        state1 = create_neutral_emotional_state()
        state2 = EmotionalState(valence=0.5, arousal=0.7, dominance=0.3, primary_emotion="curious")
        assert emotional_similarity(state1, state2) == emotional_similarity(state2, state1)


# ============================================================================
# CognitivePathway Tests
# ============================================================================


class TestCognitivePathway:
    """Test suite for CognitivePathway."""

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM client."""
        client = AsyncMock()
        response = MagicMock()
        response.content = json.dumps({
            "understanding": "User is asking about weather",
            "user_intent": "informational_query",
            "topics": ["weather"],
            "entities": ["London"],
            "reasoning": "User wants to know the weather",
            "relevance_score": 0.8,
        })
        client.chat.return_value = response
        return client

    @pytest.fixture
    def cognitive_pathway(self, mock_llm_client):
        """Create CognitivePathway with mocked LLM client."""
        return CognitivePathway(llm_client=mock_llm_client)

    @pytest.fixture
    def working_memory(self):
        """Create working memory with sample messages."""
        wm = WorkingMemory(max_size=5)
        wm.add("user", "Hello there")
        wm.add("assistant", "Hi! How can I help?")
        return wm

    @pytest.mark.asyncio
    async def test_process_success(self, cognitive_pathway, working_memory):
        """Test successful cognitive processing."""
        result = await cognitive_pathway.process("What's the weather like?", working_memory)

        assert isinstance(result, CognitiveOutput)
        assert result.understanding == "User is asking about weather"
        assert result.user_intent == "informational_query"
        assert result.topics == ["weather"]
        assert result.entities == ["London"]
        assert result.relevance_score == 0.8

    @pytest.mark.asyncio
    async def test_process_with_markdown_json(self, mock_llm_client, working_memory):
        """Test processing with markdown-wrapped JSON response."""
        response = MagicMock()
        response.content = "```json\n" + json.dumps({
            "understanding": "Test understanding",
            "user_intent": "social_chat",
            "topics": ["greeting"],
            "entities": [],
            "reasoning": "Simple greeting",
            "relevance_score": 0.5,
        }) + "\n```"
        mock_llm_client.chat.return_value = response

        pathway = CognitivePathway(llm_client=mock_llm_client)
        result = await pathway.process("Hi!", working_memory)

        assert result.understanding == "Test understanding"
        assert result.user_intent == "social_chat"

    @pytest.mark.asyncio
    async def test_process_with_generic_markdown(self, mock_llm_client, working_memory):
        """Test processing with generic markdown code block."""
        response = MagicMock()
        response.content = "```\n" + json.dumps({
            "understanding": "Generic markdown",
            "user_intent": "social_chat",
            "topics": [],
            "entities": [],
            "reasoning": "",
            "relevance_score": 0.3,
        }) + "\n```"
        mock_llm_client.chat.return_value = response

        pathway = CognitivePathway(llm_client=mock_llm_client)
        result = await pathway.process("Hey", working_memory)

        assert result.understanding == "Generic markdown"

    @pytest.mark.asyncio
    async def test_process_malformed_json_fallback(self, mock_llm_client, working_memory):
        """Test fallback when LLM returns malformed JSON."""
        response = MagicMock()
        response.content = "This is not JSON at all"
        mock_llm_client.chat.return_value = response

        pathway = CognitivePathway(llm_client=mock_llm_client)
        result = await pathway.process("Hello?", working_memory)

        assert isinstance(result, CognitiveOutput)
        assert result.user_intent == ""

    @pytest.mark.asyncio
    async def test_process_llm_exception_fallback(self, mock_llm_client, working_memory):
        """Test fallback when LLM raises exception."""
        mock_llm_client.chat.side_effect = Exception("LLM Error")

        pathway = CognitivePathway(llm_client=mock_llm_client)
        result = await pathway.process("Hello", working_memory)

        assert isinstance(result, CognitiveOutput)
        assert result.relevance_score == 0.5
        assert "Fallback" in result.reasoning

    @pytest.mark.asyncio
    async def test_process_empty_working_memory(self, cognitive_pathway):
        """Test processing with empty working memory."""
        empty_wm = WorkingMemory(max_size=5)
        result = await cognitive_pathway.process("Hello", empty_wm)

        assert isinstance(result, CognitiveOutput)

    def test_build_context_with_messages(self, cognitive_pathway, working_memory):
        """Test context building with messages."""
        context = cognitive_pathway._build_context(working_memory)
        assert "User: Hello there" in context
        assert "Assistant: Hi! How can I help?" in context

    def test_build_context_empty(self, cognitive_pathway):
        """Test context building with empty working memory."""
        empty_wm = WorkingMemory(max_size=5)
        context = cognitive_pathway._build_context(empty_wm)
        assert context == "No prior conversation context."

    def test_build_context_with_message_objects(self, cognitive_pathway):
        """Test context building with Message-like objects."""
        # Create a mock working memory with Message-like objects
        class MockMessage:
            def __init__(self, role, content):
                self.role = role
                self.content = content

        wm = WorkingMemory(max_size=5)
        # Manually add mock messages (bypassing the add method)
        wm.messages.append(MockMessage("user", "Test message"))

        context = cognitive_pathway._build_context(wm)
        assert "User: Test message" in context

    def test_parse_json_response_plain(self, cognitive_pathway):
        """Test parsing plain JSON."""
        data = {"key": "value"}
        result = cognitive_pathway._parse_json_response(json.dumps(data))
        assert result == data

    def test_parse_json_response_markdown_json(self, cognitive_pathway):
        """Test parsing markdown JSON block."""
        data = {"key": "value"}
        content = f"```json\n{json.dumps(data)}\n```"
        result = cognitive_pathway._parse_json_response(content)
        assert result == data

    def test_parse_json_response_generic_markdown(self, cognitive_pathway):
        """Test parsing generic markdown block."""
        data = {"key": "value"}
        content = f"```\n{json.dumps(data)}\n```"
        result = cognitive_pathway._parse_json_response(content)
        assert result == data

    def test_parse_json_response_invalid(self, cognitive_pathway):
        """Test parsing invalid JSON returns empty dict."""
        result = cognitive_pathway._parse_json_response("not json")
        assert result == {}

    def test_fallback_cognitive_processing_informational(self, cognitive_pathway):
        """Test fallback for informational query."""
        wm = WorkingMemory(max_size=5)
        result = cognitive_pathway._fallback_cognitive_processing("What is Python?", wm)

        assert result.user_intent == "informational_query"
        assert "Python" in result.entities

    def test_fallback_cognitive_processing_emotional(self, cognitive_pathway):
        """Test fallback for emotional support."""
        wm = WorkingMemory(max_size=5)
        result = cognitive_pathway._fallback_cognitive_processing("I feel sad", wm)

        assert result.user_intent == "emotional_support"

    def test_fallback_cognitive_processing_action(self, cognitive_pathway):
        """Test fallback for action request."""
        wm = WorkingMemory(max_size=5)
        result = cognitive_pathway._fallback_cognitive_processing("Please do this for me", wm)

        assert result.user_intent == "action_request"

    def test_fallback_cognitive_processing_social(self, cognitive_pathway):
        """Test fallback for social chat."""
        wm = WorkingMemory(max_size=5)
        result = cognitive_pathway._fallback_cognitive_processing("Nice weather today", wm)

        assert result.user_intent == "social_chat"

    def test_fallback_cognitive_processing_entity_extraction(self, cognitive_pathway):
        """Test entity extraction in fallback."""
        wm = WorkingMemory(max_size=5)
        result = cognitive_pathway._fallback_cognitive_processing("I visited Paris and London", wm)

        assert "Paris" in result.entities
        assert "London" in result.entities


# ============================================================================
# EmotionalPathway Tests
# ============================================================================


class TestEmotionalPathway:
    """Test suite for EmotionalPathway."""

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM client."""
        client = AsyncMock()
        response = MagicMock()
        response.content = json.dumps({
            "detected_emotions": [
                {"label": "joy", "intensity": 0.8, "valence": 0.8, "arousal": 0.6, "dominance": 0.6},
                {"label": "surprise", "intensity": 0.4, "valence": 0.2, "arousal": 0.8, "dominance": 0.5},
            ],
            "emotional_reaction": "feeling happy for the user",
            "appropriate_response_tone": "warm",
            "affect_influence": 0.6,
        })
        client.chat.return_value = response
        return client

    @pytest.fixture
    def emotional_pathway(self, mock_llm_client):
        """Create EmotionalPathway with mocked LLM client."""
        return EmotionalPathway(llm_client=mock_llm_client)

    @pytest.fixture
    def cognitive_output(self):
        """Create sample cognitive output."""
        return CognitiveOutput(
            understanding="User got promoted",
            user_intent="social_chat",
            topics=["career"],
            entities=["Company"],
            reasoning="User is sharing good news",
        )

    @pytest.fixture
    def current_emotional_state(self):
        """Create sample emotional state."""
        return create_neutral_emotional_state()

    @pytest.mark.asyncio
    async def test_process_success(
        self, emotional_pathway, cognitive_output, current_emotional_state
    ):
        """Test successful emotional processing."""
        result = await emotional_pathway.process(
            "I got promoted!",
            cognitive_output,
            current_emotional_state,
        )

        assert isinstance(result, EmotionalOutput)
        assert len(result.detected_emotions) == 2
        assert result.detected_emotions[0]["label"] == "joy"
        assert result.emotional_reaction == "feeling happy for the user"
        assert result.appropriate_response_tone == "warm"
        assert result.affect_influence == 0.6

    @pytest.mark.asyncio
    async def test_process_with_missing_vad(
        self, mock_llm_client, cognitive_output, current_emotional_state
    ):
        """Test processing when emotions lack VAD values."""
        response = MagicMock()
        response.content = json.dumps({
            "detected_emotions": [
                {"label": "happy", "intensity": 0.7},
            ],
            "emotional_reaction": "feeling good",
            "appropriate_response_tone": "warm",
            "affect_influence": 0.5,
        })
        mock_llm_client.chat.return_value = response

        pathway = EmotionalPathway(llm_client=mock_llm_client)
        result = await pathway.process("Great day!", cognitive_output, current_emotional_state)

        assert len(result.detected_emotions) == 1
        # VAD should be interpolated and added to first emotion
        assert "valence" in result.detected_emotions[0]
        assert "arousal" in result.detected_emotions[0]

    @pytest.mark.asyncio
    async def test_process_llm_exception_fallback(
        self, mock_llm_client, cognitive_output, current_emotional_state
    ):
        """Test fallback when LLM raises exception."""
        mock_llm_client.chat.side_effect = Exception("LLM Error")

        pathway = EmotionalPathway(llm_client=mock_llm_client)
        result = await pathway.process("I am happy!", cognitive_output, current_emotional_state)

        assert isinstance(result, EmotionalOutput)
        assert len(result.detected_emotions) > 0
        assert result.detected_emotions[0]["label"] == "joy"

    @pytest.mark.asyncio
    async def test_process_empty_emotions(self, mock_llm_client, cognitive_output, current_emotional_state):
        """Test processing with empty emotions from LLM."""
        response = MagicMock()
        response.content = json.dumps({
            "detected_emotions": [],
            "emotional_reaction": "",
            "appropriate_response_tone": "neutral",
            "affect_influence": 0.2,
        })
        mock_llm_client.chat.return_value = response

        pathway = EmotionalPathway(llm_client=mock_llm_client)
        result = await pathway.process("Okay.", cognitive_output, current_emotional_state)

        assert result.detected_emotions == []
        assert result.affect_influence == 0.2

    def test_update_emotional_state_with_emotions(
        self, emotional_pathway, current_emotional_state
    ):
        """Test emotional state update with detected emotions."""
        emotional_output = EmotionalOutput(
            detected_emotions=[
                {"label": "joy", "intensity": 0.8, "valence": 0.8, "arousal": 0.6, "dominance": 0.6},
            ],
            emotional_reaction="feeling happy",
            appropriate_response_tone="warm",
            affect_influence=0.5,
        )

        new_state = emotional_pathway.update_emotional_state(
            current_emotional_state,
            emotional_output,
            time_delta=60.0,  # 1 minute
        )

        assert isinstance(new_state, EmotionalState)
        assert new_state.valence > current_emotional_state.valence  # Shifted toward joy
        assert new_state.intensity > current_emotional_state.intensity
        assert new_state.primary_emotion == "joy"

    def test_update_emotional_state_no_emotions(
        self, emotional_pathway, current_emotional_state
    ):
        """Test emotional state update with no emotions."""
        emotional_output = EmotionalOutput(
            detected_emotions=[],
            emotional_reaction="",
            appropriate_response_tone="neutral",
            affect_influence=0.2,
        )

        new_state = emotional_pathway.update_emotional_state(
            current_emotional_state,
            emotional_output,
            time_delta=60.0,
        )

        assert isinstance(new_state, EmotionalState)
        # Should decay toward neutral
        assert new_state.intensity < current_emotional_state.intensity

    def test_update_emotional_state_time_delta_zero(
        self, emotional_pathway, current_emotional_state
    ):
        """Test emotional state update with zero time delta."""
        emotional_output = EmotionalOutput(
            detected_emotions=[
                {"label": "angry", "intensity": 0.9, "valence": -0.7, "arousal": 0.8, "dominance": 0.8},
            ],
            emotional_reaction="feeling angry",
            appropriate_response_tone="assertive",
            affect_influence=0.7,
        )

        new_state = emotional_pathway.update_emotional_state(
            current_emotional_state,
            emotional_output,
            time_delta=0.0,
        )

        assert isinstance(new_state, EmotionalState)
        # No decay, so intensity should be higher
        assert new_state.intensity > 0.0

    def test_update_emotional_state_long_time_decay(
        self, emotional_pathway, current_emotional_state
    ):
        """Test emotional state decays significantly over long time."""
        emotional_output = EmotionalOutput(
            detected_emotions=[],
            emotional_reaction="",
            appropriate_response_tone="neutral",
            affect_influence=0.2,
        )

        new_state = emotional_pathway.update_emotional_state(
            current_emotional_state,
            emotional_output,
            time_delta=3600.0,  # 1 hour
        )

        # Should decay toward neutral intensity
        assert new_state.intensity < current_emotional_state.intensity
        assert new_state.primary_emotion == "neutral"

    def test_update_emotional_state_secondary_emotions(
        self, emotional_pathway, current_emotional_state
    ):
        """Test secondary emotions are preserved."""
        emotional_output = EmotionalOutput(
            detected_emotions=[
                {"label": "joy", "intensity": 0.8, "valence": 0.8, "arousal": 0.6, "dominance": 0.6},
                {"label": "surprise", "intensity": 0.5, "valence": 0.2, "arousal": 0.8, "dominance": 0.5},
                {"label": "pride", "intensity": 0.3, "valence": 0.7, "arousal": 0.5, "dominance": 0.8},
            ],
            emotional_reaction="feeling joyful and surprised",
            appropriate_response_tone="warm",
            affect_influence=0.6,
        )

        new_state = emotional_pathway.update_emotional_state(
            current_emotional_state,
            emotional_output,
            time_delta=30.0,
        )

        assert len(new_state.secondary_emotions) > 0
        assert "surprise" in new_state.secondary_emotions

    def test_update_emotional_state_low_intensity_becomes_neutral(
        self, emotional_pathway, current_emotional_state
    ):
        """Test that very low intensity reverts to neutral."""
        emotional_output = EmotionalOutput(
            detected_emotions=[
                {"label": "joy", "intensity": 0.01, "valence": 0.8, "arousal": 0.6, "dominance": 0.6},
            ],
            emotional_reaction="",
            appropriate_response_tone="neutral",
            affect_influence=0.1,
        )

        new_state = emotional_pathway.update_emotional_state(
            current_emotional_state,
            emotional_output,
            time_delta=3600.0,
        )

        assert new_state.primary_emotion == "neutral"
        assert new_state.secondary_emotions == []

    def test_build_emotional_context(
        self, emotional_pathway, cognitive_output, current_emotional_state
    ):
        """Test emotional context building."""
        context = emotional_pathway._build_emotional_context(
            cognitive_output, current_emotional_state
        )

        assert "Current character emotional state:" in context
        assert "neutral" in context
        assert "social_chat" in context
        assert "career" in context

    def test_parse_json_response_plain(self, emotional_pathway):
        """Test parsing plain JSON."""
        data = {"key": "value"}
        result = emotional_pathway._parse_json_response(json.dumps(data))
        assert result == data

    def test_parse_json_response_markdown(self, emotional_pathway):
        """Test parsing markdown-wrapped JSON."""
        data = {"key": "value"}
        content = f"```json\n{json.dumps(data)}\n```"
        result = emotional_pathway._parse_json_response(content)
        assert result == data

    def test_parse_json_response_invalid(self, emotional_pathway):
        """Test parsing invalid JSON returns empty dict."""
        result = emotional_pathway._parse_json_response("not json")
        assert result == {}

    def test_fallback_emotional_processing_positive(
        self, emotional_pathway, current_emotional_state
    ):
        """Test fallback for positive input."""
        result = emotional_pathway._fallback_emotional_processing(
            "I am so happy today!",
            current_emotional_state,
        )

        assert result.detected_emotions[0]["label"] == "joy"
        assert result.emotional_reaction == "feeling happy for the user"
        assert result.appropriate_response_tone == "warm"

    def test_fallback_emotional_processing_negative(
        self, emotional_pathway, current_emotional_state
    ):
        """Test fallback for negative input."""
        result = emotional_pathway._fallback_emotional_processing(
            "I feel sad and angry",
            current_emotional_state,
        )

        assert any(e["label"] in ["sadness", "joy"] for e in result.detected_emotions)

    def test_fallback_emotional_processing_anxious(
        self, emotional_pathway, current_emotional_state
    ):
        """Test fallback for anxious input."""
        result = emotional_pathway._fallback_emotional_processing(
            "I am worried and nervous",
            current_emotional_state,
        )

        assert result.detected_emotions[0]["label"] == "anxiety"
        assert result.appropriate_response_tone == "concerned"

    def test_fallback_emotional_processing_neutral(
        self, emotional_pathway, current_emotional_state
    ):
        """Test fallback for neutral input."""
        result = emotional_pathway._fallback_emotional_processing(
            "The sky is blue",
            current_emotional_state,
        )

        assert result.detected_emotions[0]["label"] == "neutral"
        assert result.appropriate_response_tone == "neutral"

    def test_fallback_emotional_processing_mixed(
        self, emotional_pathway, current_emotional_state
    ):
        """Test fallback with mixed emotional words."""
        result = emotional_pathway._fallback_emotional_processing(
            "I love this but feel anxious",
            current_emotional_state,
        )

        labels = [e["label"] for e in result.detected_emotions]
        assert "joy" in labels
        assert "anxiety" in labels


# ============================================================================
# FusionLayer Tests
# ============================================================================


class TestFusionLayer:
    """Test suite for FusionLayer."""

    @pytest.fixture
    def fusion_layer(self):
        """Create FusionLayer instance."""
        return FusionLayer()

    @pytest.fixture
    def cognitive_output(self):
        """Create sample cognitive output."""
        return CognitiveOutput(
            understanding="User is asking for help",
            user_intent="emotional_support",
            topics=["support"],
            entities=[],
            reasoning="User needs emotional support",
        )

    @pytest.fixture
    def emotional_output(self):
        """Create sample emotional output."""
        return EmotionalOutput(
            detected_emotions=[
                {"label": "sad", "intensity": 0.7, "valence": -0.7, "arousal": 0.3, "dominance": 0.3},
            ],
            emotional_reaction="feeling concerned",
            appropriate_response_tone="somber",
            affect_influence=0.7,
        )

    @pytest.fixture
    def current_state(self):
        """Create sample current emotional state."""
        return create_neutral_emotional_state()

    def test_merge_basic(self, fusion_layer, cognitive_output, emotional_output, current_state):
        """Test basic fusion."""
        result = fusion_layer.merge(cognitive_output, emotional_output, current_state)

        assert isinstance(result, FusedState)
        assert result.cognitive == cognitive_output
        assert result.emotional == emotional_output
        assert isinstance(result.fused_emotional_state, EmotionalState)
        assert result.response_guidance != ""

    def test_merge_no_emotions(self, fusion_layer, cognitive_output, current_state):
        """Test fusion with no detected emotions."""
        empty_emotional = EmotionalOutput(
            detected_emotions=[],
            emotional_reaction="",
            appropriate_response_tone="neutral",
            affect_influence=0.2,
        )

        result = fusion_layer.merge(cognitive_output, empty_emotional, current_state)

        assert isinstance(result, FusedState)
        assert result.fused_emotional_state == current_state

    def test_fuse_emotional_state(self, fusion_layer, emotional_output, current_state):
        """Test emotional state fusion."""
        fused = fusion_layer._fuse_emotional_state(current_state, emotional_output)

        assert isinstance(fused, EmotionalState)
        # Should be influenced by sad emotion (negative valence)
        assert fused.valence < current_state.valence

    def test_fuse_emotional_state_high_influence(
        self, fusion_layer, current_state
    ):
        """Test fusion with high affect influence."""
        high_influence_emotional = EmotionalOutput(
            detected_emotions=[
                {"label": "angry", "intensity": 0.9, "valence": -0.7, "arousal": 0.8, "dominance": 0.8},
            ],
            emotional_reaction="feeling angry",
            appropriate_response_tone="assertive",
            affect_influence=0.9,
        )

        fused = fusion_layer._fuse_emotional_state(current_state, high_influence_emotional)

        # High influence should strongly shift toward angry
        assert fused.valence < 0.0
        assert fused.arousal > 0.5

    def test_generate_response_guidance_full(self, fusion_layer, cognitive_output, emotional_output):
        """Test response guidance generation with all components."""
        fused_state = fusion_layer._fuse_emotional_state(
            create_neutral_emotional_state(), emotional_output
        )

        guidance = fusion_layer._generate_response_guidance(
            cognitive_output, emotional_output, fused_state
        )

        assert "User intent:" in guidance
        assert "Character is feeling" in guidance
        assert "Response tone:" in guidance
        assert "High emotional influence" in guidance
        assert "Reasoning:" in guidance

    def test_generate_response_guidance_low_influence(self, fusion_layer, cognitive_output):
        """Test response guidance with low affect influence."""
        low_influence_emotional = EmotionalOutput(
            detected_emotions=[
                {"label": "neutral", "intensity": 0.3},
            ],
            emotional_reaction="",
            appropriate_response_tone="neutral",
            affect_influence=0.2,
        )
        fused_state = create_neutral_emotional_state()

        guidance = fusion_layer._generate_response_guidance(
            cognitive_output, low_influence_emotional, fused_state
        )

        assert "Low emotional influence" in guidance

    def test_generate_response_guidance_balanced(self, fusion_layer, cognitive_output):
        """Test response guidance with balanced affect influence."""
        balanced_emotional = EmotionalOutput(
            detected_emotions=[
                {"label": "happy", "intensity": 0.5},
            ],
            emotional_reaction="feeling good",
            appropriate_response_tone="warm",
            affect_influence=0.5,
        )
        fused_state = create_neutral_emotional_state()

        guidance = fusion_layer._generate_response_guidance(
            cognitive_output, balanced_emotional, fused_state
        )

        assert "Balanced approach" in guidance

    def test_generate_response_guidance_no_intent(self, fusion_layer, emotional_output):
        """Test guidance when cognitive output has no intent."""
        empty_cognitive = CognitiveOutput()
        fused_state = create_neutral_emotional_state()

        guidance = fusion_layer._generate_response_guidance(
            empty_cognitive, emotional_output, fused_state
        )

        assert "User intent:" not in guidance

    def test_generate_response_guidance_neutral_emotion(self, fusion_layer, cognitive_output):
        """Test guidance when fused state is neutral."""
        neutral_emotional = EmotionalOutput(
            detected_emotions=[{"label": "neutral", "intensity": 0.3}],
            emotional_reaction="",
            appropriate_response_tone="neutral",
            affect_influence=0.2,
        )
        fused_state = create_neutral_emotional_state()

        guidance = fusion_layer._generate_response_guidance(
            cognitive_output, neutral_emotional, fused_state
        )

        # Should not include "Character is feeling" for neutral
        assert "Character is feeling" not in guidance

    def test_generate_response_guidance_with_tone_from_emotional(
        self, fusion_layer, cognitive_output
    ):
        """Test that emotional tone is used when available."""
        emotional = EmotionalOutput(
            detected_emotions=[{"label": "happy", "intensity": 0.8}],
            emotional_reaction="feeling happy",
            appropriate_response_tone="enthusiastic",
            affect_influence=0.6,
        )
        # Create a fused state that would map to a different tone
        fused_state = EmotionalState(
            valence=-0.5,
            arousal=0.8,
            dominance=0.6,
            primary_emotion="angry",
            intensity=0.7,
        )

        guidance = fusion_layer._generate_response_guidance(
            cognitive_output, emotional, fused_state
        )

        # Should use the emotional output's tone, not the determined tone
        assert "Response tone: enthusiastic" in guidance


# ============================================================================
# CognitiveEmotionalEngine Tests
# ============================================================================


class TestCognitiveEmotionalEngine:
    """Test suite for CognitiveEmotionalEngine."""

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM client."""
        client = AsyncMock()

        # Cognitive response
        cognitive_response = MagicMock()
        cognitive_response.content = json.dumps({
            "understanding": "User is greeting",
            "user_intent": "social_chat",
            "topics": ["greeting"],
            "entities": [],
            "reasoning": "Simple greeting",
            "relevance_score": 0.5,
        })

        # Emotional response
        emotional_response = MagicMock()
        emotional_response.content = json.dumps({
            "detected_emotions": [
                {"label": "happy", "intensity": 0.6, "valence": 0.8, "arousal": 0.6, "dominance": 0.6},
            ],
            "emotional_reaction": "feeling friendly",
            "appropriate_response_tone": "warm",
            "affect_influence": 0.4,
        })

        # Return different responses for different calls
        async def mock_chat(*args, **kwargs):
            # Check the system message to determine which pathway
            messages = args[0]
            system_content = messages[0]["content"]
            if "cognitive analysis" in system_content:
                return cognitive_response
            else:
                return emotional_response

        client.chat.side_effect = mock_chat
        return client

    @pytest.fixture
    def engine(self, mock_llm_client):
        """Create CognitiveEmotionalEngine with mocked LLM client."""
        return CognitiveEmotionalEngine(llm_client=mock_llm_client)

    @pytest.fixture
    def working_memory(self):
        """Create working memory with sample messages."""
        wm = WorkingMemory(max_size=5)
        wm.add("user", "Hello")
        wm.add("assistant", "Hi there!")
        return wm

    def test_initialization(self, engine):
        """Test engine initialization."""
        assert engine.llm_client is not None
        assert engine.cognitive_pathway is not None
        assert engine.emotional_pathway is not None
        assert engine.fusion_layer is not None
        assert isinstance(engine.emotional_state, EmotionalState)
        assert engine.last_update_time is not None

    def test_initialization_with_custom_state(self, mock_llm_client):
        """Test engine initialization with custom emotional state."""
        custom_state = EmotionalState(
            valence=0.8,
            arousal=0.7,
            dominance=0.6,
            primary_emotion="happy",
            intensity=0.8,
        )
        engine = CognitiveEmotionalEngine(
            llm_client=mock_llm_client,
            initial_emotional_state=custom_state,
        )

        assert engine.emotional_state == custom_state

    @pytest.mark.asyncio
    async def test_process_full_pipeline(self, engine, working_memory):
        """Test full processing pipeline."""
        result = await engine.process("Hello!", working_memory)

        assert isinstance(result, FusedState)
        assert isinstance(result.cognitive, CognitiveOutput)
        assert isinstance(result.emotional, EmotionalOutput)
        assert isinstance(result.fused_emotional_state, EmotionalState)
        assert result.response_guidance != ""

        # Verify emotional state was updated
        assert engine.emotional_state is not None

    @pytest.mark.asyncio
    async def test_process_updates_last_update_time(self, engine, working_memory):
        """Test that process updates last_update_time."""
        old_time = engine.last_update_time

        # Small delay to ensure time changes
        import asyncio
        await asyncio.sleep(0.01)

        await engine.process("Hello", working_memory)

        assert engine.last_update_time > old_time

    @pytest.mark.asyncio
    async def test_process_empty_working_memory(self, engine):
        """Test processing with empty working memory."""
        empty_wm = WorkingMemory(max_size=5)
        result = await engine.process("Hello", empty_wm)

        assert isinstance(result, FusedState)

    def test_get_current_emotional_state(self, engine):
        """Test getting current emotional state."""
        state = engine.get_current_emotional_state()

        assert isinstance(state, EmotionalState)
        assert state == engine.emotional_state

    def test_reset_emotional_state_default(self, engine):
        """Test resetting emotional state to default neutral."""
        # First set a non-neutral state
        engine.emotional_state = EmotionalState(
            valence=0.8,
            arousal=0.7,
            dominance=0.6,
            primary_emotion="happy",
            intensity=0.8,
        )

        engine.reset_emotional_state()

        assert engine.emotional_state.primary_emotion == "neutral"
        assert engine.emotional_state.valence == 0.0
        assert engine.emotional_state.arousal == 0.5
        assert engine.emotional_state.dominance == 0.5

    def test_reset_emotional_state_custom(self, engine):
        """Test resetting emotional state to custom state."""
        custom_state = EmotionalState(
            valence=-0.5,
            arousal=0.3,
            dominance=0.4,
            primary_emotion="sad",
            intensity=0.6,
        )

        engine.reset_emotional_state(custom_state)

        assert engine.emotional_state == custom_state

    def test_set_emotional_state(self, engine):
        """Test directly setting emotional state."""
        new_state = EmotionalState(
            valence=0.9,
            arousal=0.8,
            dominance=0.7,
            primary_emotion="excited",
            intensity=0.9,
        )

        engine.set_emotional_state(new_state)

        assert engine.emotional_state == new_state
        assert engine.last_update_time is not None

    @pytest.mark.asyncio
    async def test_process_multiple_calls(self, engine, working_memory):
        """Test processing multiple times updates state correctly."""
        result1 = await engine.process("Hello", working_memory)
        result2 = await engine.process("How are you?", working_memory)

        assert isinstance(result1, FusedState)
        assert isinstance(result2, FusedState)
        # Second call should have different state due to time delta

    @pytest.mark.asyncio
    async def test_process_with_malformed_llm_response(self, mock_llm_client, working_memory):
        """Test processing with malformed LLM response uses fallback."""
        mock_llm_client.chat.return_value = MagicMock(content="not json")

        engine = CognitiveEmotionalEngine(llm_client=mock_llm_client)
        result = await engine.process("Hello", working_memory)

        assert isinstance(result, FusedState)
        assert result.cognitive.user_intent is not None


# ============================================================================
# Edge Case Tests
# ============================================================================


class TestEdgeCases:
    """Edge case tests for the cognitive-emotional engine."""

    def test_vad_to_emotion_label_boundary(self):
        """Test VAD to emotion at boundaries."""
        # Test exact neutral
        result = vad_to_emotion_label(0.0, 0.5, 0.5)
        assert result == "neutral"

        result = vad_to_emotion_label(1.0, 1.0, 1.0)
        assert result == "excited"

        result = vad_to_emotion_label(-1.0, 0.0, 0.0)
        assert result == "depressed"

    def test_interpolate_vad_with_none_values(self):
        """Test interpolate_vad handles None values by raising TypeError."""
        emotions = [
            {"label": "happy", "intensity": None},
        ]
        with pytest.raises(TypeError):
            interpolate_vad(emotions)

    def test_emotional_state_duration_accumulation(self):
        """Test that emotional state duration accumulates."""
        pathway = EmotionalPathway(llm_client=AsyncMock())
        current = create_neutral_emotional_state()
        current.duration_seconds = 60.0

        emotional_output = EmotionalOutput(
            detected_emotions=[{"label": "happy", "intensity": 0.5}],
            emotional_reaction="",
            appropriate_response_tone="warm",
            affect_influence=0.4,
        )

        new_state = pathway.update_emotional_state(current, emotional_output, time_delta=30.0)
        assert new_state.duration_seconds == 90.0

    def test_fusion_layer_with_multiple_secondary_emotions(self):
        """Test fusion layer handles multiple secondary emotions."""
        fusion = FusionLayer()
        current = create_neutral_emotional_state()

        emotional = EmotionalOutput(
            detected_emotions=[
                {"label": "happy", "intensity": 0.8, "valence": 0.8, "arousal": 0.6, "dominance": 0.6},
                {"label": "surprise", "intensity": 0.5, "valence": 0.2, "arousal": 0.8, "dominance": 0.5},
                {"label": "pride", "intensity": 0.4, "valence": 0.7, "arousal": 0.5, "dominance": 0.8},
                {"label": "relief", "intensity": 0.3, "valence": 0.6, "arousal": 0.3, "dominance": 0.5},
            ],
            emotional_reaction="",
            appropriate_response_tone="warm",
            affect_influence=0.5,
        )

        fused = fusion._fuse_emotional_state(current, emotional)
        assert len(fused.secondary_emotions) <= 3

    def test_cognitive_pathway_with_very_long_input(self):
        """Test cognitive pathway with very long user input."""
        client = AsyncMock()
        client.chat.return_value = MagicMock(content="not json")

        pathway = CognitivePathway(llm_client=client)
        wm = WorkingMemory(max_size=5)

        long_input = "Hello " * 1000
        result = pathway._fallback_cognitive_processing(long_input, wm)

        assert len(result.understanding) <= 120
        assert result.user_intent is not None

    def test_emotional_pathway_with_very_long_input(self):
        """Test emotional pathway with very long user input."""
        pathway = EmotionalPathway(llm_client=AsyncMock())
        state = create_neutral_emotional_state()

        long_input = "happy " * 1000
        result = pathway._fallback_emotional_processing(long_input, state)

        assert result.detected_emotions[0]["label"] == "joy"

    def test_emotional_similarity_same_state(self):
        """Test emotional similarity with the same state object."""
        state = create_neutral_emotional_state()
        assert emotional_similarity(state, state) == 1.0

    def test_emotional_distance_zero_for_identical(self):
        """Test emotional distance is zero for identical states."""
        state1 = create_neutral_emotional_state()
        state2 = create_neutral_emotional_state()
        assert emotional_distance(state1, state2) == 0.0

    @pytest.mark.asyncio
    async def test_cognitive_pathway_empty_string_input(self):
        """Test cognitive pathway with empty string input."""
        client = AsyncMock()
        client.chat.return_value = MagicMock(content="not json")

        pathway = CognitivePathway(llm_client=client)
        wm = WorkingMemory(max_size=5)

        result = await pathway.process("", wm)

        assert isinstance(result, CognitiveOutput)

    @pytest.mark.asyncio
    async def test_emotional_pathway_empty_string_input(self):
        """Test emotional pathway with empty string input."""
        client = AsyncMock()
        client.chat.return_value = MagicMock(content="not json")

        pathway = EmotionalPathway(llm_client=client)
        cognitive = CognitiveOutput()
        state = create_neutral_emotional_state()

        result = await pathway.process("", cognitive, state)

        assert isinstance(result, EmotionalOutput)

    def test_determine_response_tone_exact_thresholds(self):
        """Test determine_response_tone at exact thresholds."""
        for (t_v, t_a, t_d), expected_tone in TONE_MAPPINGS:
            tone = determine_response_tone(t_v, t_a, t_d)
            if expected_tone == "concerned":
                assert tone in ("somber", "concerned")
            elif expected_tone == "confident":
                assert tone in ("warm", "confident")
            elif expected_tone == "neutral":
                assert tone in ("somber", "neutral")
            else:
                assert tone == expected_tone

    def test_create_neutral_emotional_state_unique_instances(self):
        """Test that create_neutral_emotional_state returns unique instances."""
        state1 = create_neutral_emotional_state()
        state2 = create_neutral_emotional_state()

        assert state1 is not state2
        assert state1.valence == state2.valence
        assert state1.arousal == state2.arousal
        assert state1.dominance == state2.dominance
        assert state1.primary_emotion == state2.primary_emotion

    def test_working_memory_with_dict_messages_in_context(self):
        """Test working memory with dict messages in _build_context."""
        pathway = CognitivePathway(llm_client=AsyncMock())
        wm = WorkingMemory(max_size=5)
        wm.add("user", "Hello")
        wm.add("assistant", "Hi")

        context = pathway._build_context(wm)
        assert "User: Hello" in context
        assert "Assistant: Hi" in context

    @pytest.mark.asyncio
    async def test_engine_process_time_delta_zero(self):
        """Test engine process with effectively zero time delta."""
        client = AsyncMock()
        response = MagicMock()
        response.content = json.dumps({
            "understanding": "Test",
            "user_intent": "social_chat",
            "topics": [],
            "entities": [],
            "reasoning": "",
            "relevance_score": 0.5,
        })
        client.chat.return_value = response

        engine = CognitiveEmotionalEngine(llm_client=client)
        wm = WorkingMemory(max_size=5)
        engine.last_update_time = datetime.now()

        result = await engine.process("Hello", wm)
        assert isinstance(result, FusedState)

    def test_fusion_layer_response_guidance_no_reasoning(self):
        """Test guidance generation when cognitive has no reasoning."""
        fusion = FusionLayer()
        cognitive = CognitiveOutput(
            understanding="Test",
            user_intent="social_chat",
            reasoning="",
        )
        emotional = EmotionalOutput(
            detected_emotions=[{"label": "neutral", "intensity": 0.3}],
            appropriate_response_tone="neutral",
            affect_influence=0.2,
        )
        state = create_neutral_emotional_state()

        guidance = fusion._generate_response_guidance(cognitive, emotional, state)

        assert "Reasoning:" not in guidance

    def test_emotional_pathway_update_with_high_intensity(self):
        """Test emotional update with very high intensity emotion."""
        pathway = EmotionalPathway(llm_client=AsyncMock())
        current = create_neutral_emotional_state()

        emotional_output = EmotionalOutput(
            detected_emotions=[
                {"label": "furious", "intensity": 1.0, "valence": -0.9, "arousal": 0.95, "dominance": 0.9},
            ],
            emotional_reaction="feeling furious",
            appropriate_response_tone="assertive",
            affect_influence=0.9,
        )

        new_state = pathway.update_emotional_state(current, emotional_output, time_delta=0.0)

        assert new_state.intensity <= 1.0  # Should be clamped
        assert new_state.valence >= -1.0  # Should be clamped
        assert new_state.primary_emotion == "furious"

    def test_cognitive_pathway_fallback_with_special_characters(self):
        """Test fallback with special characters in input."""
        pathway = CognitivePathway(llm_client=AsyncMock())
        wm = WorkingMemory(max_size=5)

        result = pathway._fallback_cognitive_processing("Hello! @#$%^&*()", wm)

        assert isinstance(result, CognitiveOutput)
        assert result.user_intent == "social_chat"

    def test_emotional_pathway_fallback_with_special_characters(self):
        """Test emotional fallback with special characters."""
        pathway = EmotionalPathway(llm_client=AsyncMock())
        state = create_neutral_emotional_state()

        result = pathway._fallback_emotional_processing("happy! @#$%", state)

        assert result.detected_emotions[0]["label"] == "joy"

    def test_interpolate_vad_with_missing_label(self):
        """Test interpolate_vad with missing label key."""
        emotions = [
            {"intensity": 0.8, "valence": 0.5, "arousal": 0.6, "dominance": 0.7},
        ]
        v, a, d, secondary = interpolate_vad(emotions)

        # Should use default valence=0.0, arousal=0.5, dominance=0.5 since no label
        assert v == pytest.approx(0.0, abs=0.01)
        assert a == pytest.approx(0.5, abs=0.01)
        assert d == pytest.approx(0.5, abs=0.01)

    def test_emotional_state_clamping_in_update(self):
        """Test that emotional state values are clamped during update."""
        pathway = EmotionalPathway(llm_client=AsyncMock())
        current = create_neutral_emotional_state()

        emotional_output = EmotionalOutput(
            detected_emotions=[
                {"label": "custom", "intensity": 1.0, "valence": 2.0, "arousal": -1.0, "dominance": 2.0},
            ],
            emotional_reaction="",
            appropriate_response_tone="neutral",
            affect_influence=0.5,
        )

        new_state = pathway.update_emotional_state(current, emotional_output, time_delta=0.0)

        assert -1.0 <= new_state.valence <= 1.0
        assert 0.0 <= new_state.arousal <= 1.0
        assert 0.0 <= new_state.dominance <= 1.0
        assert 0.0 <= new_state.intensity <= 1.0

    def test_fusion_layer_clamping(self):
        """Test that fusion layer clamps values."""
        fusion = FusionLayer()
        current = EmotionalState(
            valence=-1.0,
            arousal=0.0,
            dominance=0.0,
            primary_emotion="sad",
            intensity=0.5,
        )

        emotional = EmotionalOutput(
            detected_emotions=[
                {"label": "custom", "intensity": 1.0, "valence": 2.0, "arousal": -1.0, "dominance": 2.0},
            ],
            emotional_reaction="",
            appropriate_response_tone="neutral",
            affect_influence=0.5,
        )

        fused = fusion._fuse_emotional_state(current, emotional)

        assert -1.0 <= fused.valence <= 1.0
        assert 0.0 <= fused.arousal <= 1.0
        assert 0.0 <= fused.dominance <= 1.0
        assert 0.0 <= fused.intensity <= 1.0

    @pytest.mark.asyncio
    async def test_cognitive_pathway_json_with_extra_text(self):
        """Test parsing JSON with extra text around it."""
        client = AsyncMock()
        response = MagicMock()
        response.content = (
            "Here is my analysis:\n\n"
            "```json\n"
            + json.dumps({
                "understanding": "Test",
                "user_intent": "social_chat",
                "topics": [],
                "entities": [],
                "reasoning": "",
                "relevance_score": 0.5,
            })
            + "\n```\n\nHope this helps!"
        )
        client.chat.return_value = response

        pathway = CognitivePathway(llm_client=client)
        wm = WorkingMemory(max_size=5)

        result = await pathway.process("Hello", wm)
        assert result.understanding == "Test"

    @pytest.mark.asyncio
    async def test_emotional_pathway_json_with_extra_text(self):
        """Test emotional pathway parsing JSON with extra text."""
        client = AsyncMock()
        response = MagicMock()
        response.content = (
            "Analysis:\n"
            "```json\n"
            + json.dumps({
                "detected_emotions": [{"label": "happy", "intensity": 0.7}],
                "emotional_reaction": "feeling good",
                "appropriate_response_tone": "warm",
                "affect_influence": 0.5,
            })
            + "\n```"
        )
        client.chat.return_value = response

        pathway = EmotionalPathway(llm_client=client)
        cognitive = CognitiveOutput()
        state = create_neutral_emotional_state()

        result = await pathway.process("Hello", cognitive, state)
        assert result.detected_emotions[0]["label"] == "happy"

    def test_cognitive_pathway_parse_json_with_nested_backticks(self):
        """Test parsing JSON with backtick characters in value."""
        pathway = CognitivePathway(llm_client=AsyncMock())

        content = '{"key": "value with `nested` markdown"}'
        result = pathway._parse_json_response(content)

        assert result == {"key": "value with `nested` markdown"}

    def test_emotional_pathway_parse_json_with_nested_backticks(self):
        """Test emotional pathway parsing JSON with backtick characters."""
        pathway = EmotionalPathway(llm_client=AsyncMock())

        content = '{"key": "value with `nested` markdown"}'
        result = pathway._parse_json_response(content)

        assert result == {"key": "value with `nested` markdown"}

    def test_emotional_pathway_secondary_emotions_filtering(self):
        """Test secondary emotions filtering in update_emotional_state."""
        pathway = EmotionalPathway(llm_client=AsyncMock())
        current = create_neutral_emotional_state()

        emotional_output = EmotionalOutput(
            detected_emotions=[
                {"label": "joy", "intensity": 0.8},
                {"label": "surprise", "intensity": 0.1},  # Too low, filtered out
                {"label": "pride", "intensity": 0.3},  # Should be included
                {"label": "gratitude", "intensity": 0.25},  # Should be included
                {"label": "love", "intensity": 0.5},  # Should be included
                {"label": "hope", "intensity": 0.4},  # Should be included but limited to top 3
            ],
            emotional_reaction="",
            appropriate_response_tone="warm",
            affect_influence=0.5,
        )

        new_state = pathway.update_emotional_state(current, emotional_output, time_delta=0.0)

        assert "surprise" not in new_state.secondary_emotions
        assert len(new_state.secondary_emotions) <= 3

    def test_fusion_layer_empty_cognitive(self):
        """Test fusion layer with empty cognitive output."""
        fusion = FusionLayer()
        cognitive = CognitiveOutput()
        emotional = EmotionalOutput(
            detected_emotions=[{"label": "neutral", "intensity": 0.3}],
            appropriate_response_tone="neutral",
            affect_influence=0.2,
        )
        state = create_neutral_emotional_state()

        result = fusion.merge(cognitive, emotional, state)

        assert isinstance(result, FusedState)
        assert result.response_guidance != ""

    def test_fusion_layer_empty_emotional(self):
        """Test fusion layer with empty emotional output."""
        fusion = FusionLayer()
        cognitive = CognitiveOutput(
            understanding="Test",
            user_intent="social_chat",
        )
        emotional = EmotionalOutput()
        state = create_neutral_emotional_state()

        result = fusion.merge(cognitive, emotional, state)

        assert isinstance(result, FusedState)
        assert result.fused_emotional_state == state
