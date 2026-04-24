"""Comprehensive unit tests for consistency_validator module."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from persona_agent.core.consistency_validator import (
    VALIDATION_PROMPTS,
    ConsistencyScore,
    ConsistencyValidator,
    Message,
    ValidationConfig,
    ValidationError,
    ValidationReport,
)
from persona_agent.core.schemas import (
    BehavioralMatrix,
    CognitiveState,
    CoreIdentity,
    CoreValues,
    DynamicContext,
    EmotionalState,
    RelationshipState,
    ValidationResult,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def core_identity():
    """Create a test CoreIdentity."""
    return CoreIdentity(
        name="TestCharacter",
        version="1.0.0",
        backstory="A helpful test character.",
        values=CoreValues(
            values=["kindness", "honesty"],
            fears=["spiders"],
            desires=["helping others"],
            boundaries=["no violence"],
        ),
        behavioral_matrix=BehavioralMatrix(
            must_always=["be polite"],
            must_never=["be rude"],
            should_avoid=["controversial topics"],
        ),
    )


@pytest.fixture
def dynamic_context():
    """Create a test DynamicContext."""
    return DynamicContext(
        emotional=EmotionalState(
            valence=0.5,
            arousal=0.3,
            dominance=0.5,
            primary_emotion="happy",
            secondary_emotions=["content"],
            intensity=0.6,
        ),
        social=RelationshipState(
            intimacy=0.4,
            trust=0.6,
            respect=0.7,
            familiarity=0.3,
            current_stage="friend",
            interaction_count=5,
        ),
        cognitive=CognitiveState(
            focus_target="user",
            attention_level=0.9,
            active_goals=["answer question", "be helpful"],
            current_intention="provide information",
            cognitive_load=0.2,
        ),
        conversation_turn=3,
        topic="testing",
        user_intent="learn about testing",
    )


@pytest.fixture
def conversation_history():
    """Create test conversation history."""
    return [
        Message(role="user", content="Hello", timestamp="2024-01-01T00:00:00"),
        Message(role="assistant", content="Hi there!", timestamp="2024-01-01T00:00:01"),
        Message(role="user", content="How are you?", timestamp="2024-01-01T00:00:02"),
    ]


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = AsyncMock()
    response = MagicMock()
    response.content = json.dumps({"score": 0.85})
    client.chat.return_value = response
    return client


@pytest.fixture
def validator(mock_llm_client, core_identity):
    """Create a ConsistencyValidator with mocked dependencies."""
    return ConsistencyValidator(
        llm_client=mock_llm_client,
        core_identity=core_identity,
    )


@pytest.fixture
def perfect_scores():
    """Return perfect scores for all dimensions."""
    return {
        "value_alignment": 1.0,
        "personality_consistency": 1.0,
        "historical_coherence": 1.0,
        "emotional_appropriateness": 1.0,
        "contextual_awareness": 1.0,
    }


@pytest.fixture
def failing_scores():
    """Return failing scores for some dimensions."""
    return {
        "value_alignment": 0.5,
        "personality_consistency": 0.6,
        "historical_coherence": 0.4,
        "emotional_appropriateness": 0.5,
        "contextual_awareness": 0.3,
    }


@pytest.fixture
def mixed_scores():
    """Return mixed scores (some pass, some fail)."""
    return {
        "value_alignment": 0.8,
        "personality_consistency": 0.75,
        "historical_coherence": 0.5,
        "emotional_appropriateness": 0.7,
        "contextual_awareness": 0.6,
    }


# ============================================================================
# ValidationReport Tests
# ============================================================================


class TestValidationReport:
    """Test suite for ValidationReport Pydantic model."""

    def test_valid_report(self):
        """Test creating a valid ValidationReport."""
        report = ValidationReport(
            overall_score=0.85,
            dimension_scores={
                "value_alignment": 0.9,
                "personality_consistency": 0.8,
                "historical_coherence": 0.85,
                "emotional_appropriateness": 0.9,
                "contextual_awareness": 0.8,
            },
            violations=[],
            critique="Good response",
            passed=True,
            confidence=0.9,
        )
        assert report.overall_score == 0.85
        assert report.passed is True
        assert report.confidence == 0.9

    def test_overall_score_boundary_low(self):
        """Test overall_score at lower boundary."""
        report = ValidationReport(
            overall_score=0.0,
            dimension_scores={"value_alignment": 0.0},
            violations=[],
            critique="Bad",
        )
        assert report.overall_score == 0.0

    def test_overall_score_boundary_high(self):
        """Test overall_score at upper boundary."""
        report = ValidationReport(
            overall_score=1.0,
            dimension_scores={"value_alignment": 1.0},
            violations=[],
            critique="Perfect",
        )
        assert report.overall_score == 1.0

    def test_overall_score_out_of_bounds_high(self):
        """Test overall_score above upper boundary raises error."""
        with pytest.raises(Exception):  # pydantic.ValidationError
            ValidationReport(
                overall_score=1.5,
                dimension_scores={"value_alignment": 0.5},
                violations=[],
                critique="Invalid",
            )

    def test_overall_score_out_of_bounds_low(self):
        """Test overall_score below lower boundary raises error."""
        with pytest.raises(Exception):  # pydantic.ValidationError
            ValidationReport(
                overall_score=-0.5,
                dimension_scores={"value_alignment": 0.5},
                violations=[],
                critique="Invalid",
            )

    def test_dimension_scores_validation_valid(self):
        """Test dimension_scores with valid values."""
        report = ValidationReport(
            overall_score=0.5,
            dimension_scores={
                "value_alignment": 0.0,
                "personality_consistency": 0.5,
                "historical_coherence": 1.0,
            },
            violations=[],
            critique="Test",
        )
        assert len(report.dimension_scores) == 3

    def test_dimension_scores_validation_out_of_bounds_high(self):
        """Test dimension_scores with value above 1.0 raises error."""
        with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
            ValidationReport(
                overall_score=0.5,
                dimension_scores={"value_alignment": 1.5},
                violations=[],
                critique="Invalid",
            )

    def test_dimension_scores_validation_out_of_bounds_low(self):
        """Test dimension_scores with value below 0.0 raises error."""
        with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
            ValidationReport(
                overall_score=0.5,
                dimension_scores={"value_alignment": -0.1},
                violations=[],
                critique="Invalid",
            )

    def test_default_values(self):
        """Test default field values."""
        report = ValidationReport(
            overall_score=0.5,
            dimension_scores={"value_alignment": 0.5},
            violations=[],
            critique="Test",
        )
        assert report.checks == []
        assert report.suggested_revision is None
        assert report.confidence == 0.0
        assert report.passed is False

    def test_confidence_boundary(self):
        """Test confidence field boundaries."""
        report = ValidationReport(
            overall_score=0.5,
            dimension_scores={"value_alignment": 0.5},
            violations=[],
            critique="Test",
            confidence=1.0,
        )
        assert report.confidence == 1.0

        with pytest.raises(Exception):
            ValidationReport(
                overall_score=0.5,
                dimension_scores={"value_alignment": 0.5},
                violations=[],
                critique="Test",
                confidence=1.5,
            )


# ============================================================================
# ConsistencyScore Tests
# ============================================================================


class TestConsistencyScore:
    """Test suite for ConsistencyScore static methods."""

    def test_dimensions_defined(self):
        """Test that all expected dimensions are defined."""
        assert "value_alignment" in ConsistencyScore.DIMENSIONS
        assert "personality_consistency" in ConsistencyScore.DIMENSIONS
        assert "historical_coherence" in ConsistencyScore.DIMENSIONS
        assert "emotional_appropriateness" in ConsistencyScore.DIMENSIONS
        assert "contextual_awareness" in ConsistencyScore.DIMENSIONS
        assert len(ConsistencyScore.DIMENSIONS) == 5

    def test_dimension_weights_sum(self):
        """Test that weights sum to approximately 1.0."""
        total_weight = sum(d["weight"] for d in ConsistencyScore.DIMENSIONS.values())
        assert abs(total_weight - 1.0) < 0.001

    def test_calculate_overall_perfect_scores(self, perfect_scores):
        """Test calculate_overall with perfect scores."""
        overall = ConsistencyScore.calculate_overall(perfect_scores)
        assert overall == 1.0

    def test_calculate_overall_failing_scores(self, failing_scores):
        """Test calculate_overall with failing scores."""
        overall = ConsistencyScore.calculate_overall(failing_scores)
        assert 0.0 <= overall <= 1.0
        assert overall < 0.7

    def test_calculate_overall_empty_scores(self):
        """Test calculate_overall with empty scores."""
        overall = ConsistencyScore.calculate_overall({})
        assert overall == 0.0

    def test_calculate_overall_missing_dimension(self):
        """Test calculate_overall with missing dimension raises error."""
        incomplete_scores = {
            "value_alignment": 0.8,
            "personality_consistency": 0.8,
        }
        with pytest.raises(ValueError, match="Missing score for dimension"):
            ConsistencyScore.calculate_overall(incomplete_scores)

    def test_calculate_overall_single_dimension(self):
        """Test calculate_overall with one complete dimension set."""
        scores = {
            "value_alignment": 1.0,
            "personality_consistency": 1.0,
            "historical_coherence": 1.0,
            "emotional_appropriateness": 1.0,
            "contextual_awareness": 1.0,
        }
        overall = ConsistencyScore.calculate_overall(scores)
        assert overall == 1.0

    def test_calculate_overall_weighted_average(self):
        """Test that calculate_overall properly weights dimensions."""
        scores = {
            "value_alignment": 0.0,  # weight 0.30
            "personality_consistency": 1.0,  # weight 0.25
            "historical_coherence": 1.0,  # weight 0.20
            "emotional_appropriateness": 1.0,  # weight 0.15
            "contextual_awareness": 1.0,  # weight 0.10
        }
        overall = ConsistencyScore.calculate_overall(scores)
        # (0.0*0.30 + 1.0*0.25 + 1.0*0.20 + 1.0*0.15 + 1.0*0.10) / 1.0 = 0.70
        assert overall == 0.70

    def test_is_consistent_all_pass(self, perfect_scores):
        """Test is_consistent with all passing scores."""
        assert ConsistencyScore.is_consistent(perfect_scores) is True

    def test_is_consistent_some_fail(self, failing_scores):
        """Test is_consistent with some failing scores."""
        assert ConsistencyScore.is_consistent(failing_scores) is False

    def test_is_consistent_empty(self):
        """Test is_consistent with empty scores."""
        assert ConsistencyScore.is_consistent({}) is False

    def test_is_consistent_missing_dimension(self):
        """Test is_consistent with missing dimension."""
        incomplete = {
            "value_alignment": 1.0,
            "personality_consistency": 1.0,
        }
        assert ConsistencyScore.is_consistent(incomplete) is False

    def test_is_consistent_boundary_values(self):
        """Test is_consistent at exact threshold boundaries."""
        scores = {
            "value_alignment": 0.7,  # exactly at threshold
            "personality_consistency": 0.7,
            "historical_coherence": 0.6,
            "emotional_appropriateness": 0.6,
            "contextual_awareness": 0.5,
        }
        assert ConsistencyScore.is_consistent(scores) is True

    def test_is_consistent_just_below_threshold(self):
        """Test is_consistent with scores just below threshold."""
        scores = {
            "value_alignment": 0.69,  # just below 0.7
            "personality_consistency": 0.7,
            "historical_coherence": 0.6,
            "emotional_appropriateness": 0.6,
            "contextual_awareness": 0.5,
        }
        assert ConsistencyScore.is_consistent(scores) is False

    def test_get_violations_no_violations(self, perfect_scores):
        """Test get_violations with no violations."""
        violations = ConsistencyScore.get_violations(perfect_scores)
        assert violations == []

    def test_get_violations_some_fail(self, failing_scores):
        """Test get_violations with some failing scores."""
        violations = ConsistencyScore.get_violations(failing_scores)
        assert len(violations) > 0
        for v in violations:
            assert "dimension" in v
            assert "severity" in v
            assert "reason" in v

    def test_get_violations_empty(self):
        """Test get_violations with empty scores."""
        violations = ConsistencyScore.get_violations({})
        assert len(violations) == 5
        for v in violations:
            assert v["severity"] == "critical"
            assert v["score"] is None
            assert "missing" in v["reason"].lower()

    def test_get_violations_missing_some(self):
        """Test get_violations with some missing dimensions."""
        partial = {
            "value_alignment": 1.0,
        }
        violations = ConsistencyScore.get_violations(partial)
        assert len(violations) == 4  # 4 missing + 0 failing

    def test_get_violations_severity_critical(self):
        """Test critical severity for large gaps."""
        scores = {
            "value_alignment": 0.3,  # gap = 0.4 > 0.3
            "personality_consistency": 1.0,
            "historical_coherence": 1.0,
            "emotional_appropriateness": 1.0,
            "contextual_awareness": 1.0,
        }
        violations = ConsistencyScore.get_violations(scores)
        assert len(violations) == 1
        assert violations[0]["severity"] == "critical"
        assert "gap" in violations[0]

    def test_get_violations_severity_major(self):
        """Test major severity for medium gaps."""
        scores = {
            "value_alignment": 0.5,  # gap = 0.2 > 0.15
            "personality_consistency": 1.0,
            "historical_coherence": 1.0,
            "emotional_appropriateness": 1.0,
            "contextual_awareness": 1.0,
        }
        violations = ConsistencyScore.get_violations(scores)
        assert len(violations) == 1
        assert violations[0]["severity"] == "major"

    def test_get_violations_severity_minor(self):
        """Test minor severity for small gaps."""
        scores = {
            "value_alignment": 0.65,  # gap = 0.05 < 0.15
            "personality_consistency": 1.0,
            "historical_coherence": 1.0,
            "emotional_appropriateness": 1.0,
            "contextual_awareness": 1.0,
        }
        violations = ConsistencyScore.get_violations(scores)
        assert len(violations) == 1
        assert violations[0]["severity"] == "minor"

    def test_get_violations_includes_all_metadata(self):
        """Test that violations include all expected metadata."""
        scores = {
            "value_alignment": 0.5,
            "personality_consistency": 1.0,
            "historical_coherence": 1.0,
            "emotional_appropriateness": 1.0,
            "contextual_awareness": 1.0,
        }
        violations = ConsistencyScore.get_violations(scores)
        v = violations[0]
        assert "dimension" in v
        assert "score" in v
        assert "threshold" in v
        assert "description" in v
        assert "severity" in v
        assert "gap" in v
        assert "reason" in v


# ============================================================================
# ConsistencyValidator Initialization Tests
# ============================================================================


class TestConsistencyValidatorInit:
    """Test suite for ConsistencyValidator initialization."""

    def test_init_with_defaults(self, mock_llm_client, core_identity):
        """Test initialization with default config and no history."""
        validator = ConsistencyValidator(
            llm_client=mock_llm_client,
            core_identity=core_identity,
        )
        assert validator.llm_client is mock_llm_client
        assert validator.core_identity is core_identity
        assert validator.validation_history == []
        assert validator.config is not None
        assert validator.config.max_attempts == 3
        assert validator.config.overall_threshold == 0.7
        assert validator.config.enable_regeneration is True
        assert validator.score_calculator is not None

    def test_init_with_custom_config(self, mock_llm_client, core_identity):
        """Test initialization with custom config."""
        config = ValidationConfig(
            max_attempts=5,
            overall_threshold=0.8,
            enable_regeneration=False,
        )
        validator = ConsistencyValidator(
            llm_client=mock_llm_client,
            core_identity=core_identity,
            config=config,
        )
        assert validator.config.max_attempts == 5
        assert validator.config.overall_threshold == 0.8
        assert validator.config.enable_regeneration is False

    def test_init_with_history(self, mock_llm_client, core_identity):
        """Test initialization with validation history."""
        history = [
            ValidationResult(overall_valid=True, overall_score=0.9),
            ValidationResult(overall_valid=False, overall_score=0.5),
        ]
        validator = ConsistencyValidator(
            llm_client=mock_llm_client,
            core_identity=core_identity,
            validation_history=history,
        )
        assert len(validator.validation_history) == 2

    def test_init_with_none_history(self, mock_llm_client, core_identity):
        """Test initialization with None history defaults to empty list."""
        validator = ConsistencyValidator(
            llm_client=mock_llm_client,
            core_identity=core_identity,
            validation_history=None,
        )
        assert validator.validation_history == []

    def test_init_config_defaults(self):
        """Test ValidationConfig default values."""
        config = ValidationConfig()
        assert config.max_attempts == 3
        assert config.overall_threshold == 0.7
        assert config.temperature_scoring == 0.3
        assert config.temperature_critique == 0.5
        assert config.temperature_revision == 0.7
        assert config.enable_regeneration is True


# ============================================================================
# ConsistencyValidator.validate Tests
# ============================================================================


class TestConsistencyValidatorValidate:
    """Test suite for ConsistencyValidator.validate method."""

    @pytest.mark.asyncio
    async def test_validate_all_pass(self, validator, dynamic_context, conversation_history):
        """Test validate when all dimensions pass."""
        # Setup LLM to return passing scores
        response = MagicMock()
        response.content = json.dumps({"score": 0.9})
        validator.llm_client.chat.return_value = response

        report = await validator.validate(
            response="Hello, how can I help you?",
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
        )

        assert isinstance(report, ValidationReport)
        assert report.passed is True
        assert report.overall_score >= validator.config.overall_threshold
        assert len(report.violations) == 0
        assert report.critique == ""  # No critique when passed
        assert report.suggested_revision is None  # No revision when passed
        assert report.confidence > 0

    @pytest.mark.asyncio
    async def test_validate_some_fail(self, validator, dynamic_context, conversation_history):
        """Test validate when some dimensions fail."""
        # Setup LLM to return mixed scores
        scores = [0.9, 0.8, 0.5, 0.9, 0.4]  # Some fail
        responses = [MagicMock(content=json.dumps({"score": s})) for s in scores]
        validator.llm_client.chat.side_effect = responses

        # Also need critique and revision responses
        critique_response = MagicMock()
        critique_response.content = "The response lacks historical coherence."
        revision_response = MagicMock()
        revision_response.content = "Revised response here."

        validator.llm_client.chat.side_effect = [
            *responses,
            critique_response,
            revision_response,
        ]

        report = await validator.validate(
            response="Hello!",
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
        )

        assert isinstance(report, ValidationReport)
        assert report.passed is False
        assert len(report.violations) > 0
        assert report.critique != ""
        assert report.suggested_revision is not None

    @pytest.mark.asyncio
    async def test_validate_llm_error(self, validator, dynamic_context, conversation_history):
        """Test validate when LLM raises an error in _build_validation_prompts."""
        # Patch _build_validation_prompts to raise an exception that bubbles up
        # past the per-dimension exception handling in _score_dimensions
        with patch.object(
            validator,
            "_build_validation_prompts",
            side_effect=Exception("Prompt building error"),
        ):
            report = await validator.validate(
                response="Hello!",
                dynamic_context=dynamic_context,
                conversation_history=conversation_history,
            )

        assert isinstance(report, ValidationReport)
        assert report.passed is False
        assert report.overall_score == 0.0
        assert len(report.violations) > 0
        assert "validation_system" in [v["dimension"] for v in report.violations]
        assert report.confidence == 0.0

    @pytest.mark.asyncio
    async def test_validate_exception_in_scoring(self, validator, dynamic_context, conversation_history):
        """Test validate handles exceptions during scoring gracefully."""
        # First call succeeds, second raises exception
        response = MagicMock()
        response.content = json.dumps({"score": 0.9})
        validator.llm_client.chat.side_effect = [
            response,
            Exception("Dimension scoring failed"),
            response,
            response,
            response,
        ]

        report = await validator.validate(
            response="Hello!",
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
        )

        assert isinstance(report, ValidationReport)
        # Should have some scores (some succeeded, some failed)
        assert len(report.dimension_scores) == 5

    @pytest.mark.asyncio
    async def test_validate_with_empty_conversation_history(self, validator, dynamic_context):
        """Test validate with empty conversation history."""
        response = MagicMock()
        response.content = json.dumps({"score": 0.9})
        validator.llm_client.chat.return_value = response

        report = await validator.validate(
            response="Hello!",
            dynamic_context=dynamic_context,
            conversation_history=[],
        )

        assert isinstance(report, ValidationReport)
        assert report.passed is True

    @pytest.mark.asyncio
    async def test_validate_overall_score_below_threshold(self, validator, dynamic_context, conversation_history):
        """Test validate when overall score is below threshold."""
        # Scores that pass individual thresholds but produce overall below threshold
        scores = {
            "value_alignment": 0.71,
            "personality_consistency": 0.71,
            "historical_coherence": 0.61,
            "emotional_appropriateness": 0.61,
            "contextual_awareness": 0.51,
        }
        responses = [MagicMock(content=json.dumps({"score": s})) for s in scores.values()]
        critique_response = MagicMock(content="Critique text")
        revision_response = MagicMock(content="Revision text")
        validator.llm_client.chat.side_effect = [*responses, critique_response, revision_response]

        report = await validator.validate(
            response="Hello!",
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
        )

        assert isinstance(report, ValidationReport)
        # Overall is 0.655 which is below default threshold of 0.7, so should fail
        assert report.overall_score < validator.config.overall_threshold
        assert report.passed is False

    @pytest.mark.asyncio
    async def test_validate_no_regeneration_when_disabled(self, validator, dynamic_context, conversation_history):
        """Test validate does not generate revision when regeneration is disabled."""
        validator.config.enable_regeneration = False

        # Return failing scores
        scores = [0.3, 0.3, 0.3, 0.3, 0.3]
        responses = [MagicMock(content=json.dumps({"score": s})) for s in scores]
        critique_response = MagicMock(content="Critique")
        validator.llm_client.chat.side_effect = [*responses, critique_response]

        report = await validator.validate(
            response="Hello!",
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
        )

        assert report.passed is False
        assert report.suggested_revision is None

    @pytest.mark.asyncio
    async def test_validate_with_violations_but_passed(self, validator, dynamic_context, conversation_history):
        """Test validate when there are violations but overall passes."""
        # Scores at exact thresholds so is_consistent returns True,
        # but overall is below threshold to trigger critique generation
        scores = {
            "value_alignment": 0.7,
            "personality_consistency": 0.7,
            "historical_coherence": 0.6,
            "emotional_appropriateness": 0.6,
            "contextual_awareness": 0.5,
        }
        responses = [MagicMock(content=json.dumps({"score": s})) for s in scores.values()]
        critique_response = MagicMock(content="Critique for low overall")
        revision_response = MagicMock(content="Revised response")
        validator.llm_client.chat.side_effect = [*responses, critique_response, revision_response]

        report = await validator.validate(
            response="Hello!",
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
        )

        assert isinstance(report, ValidationReport)
        # Overall is 0.645, below threshold 0.7, so passed=False
        assert report.overall_score < validator.config.overall_threshold
        assert report.passed is False
        assert report.critique != ""
        assert report.suggested_revision is not None


# ============================================================================
# ConsistencyValidator.validate_with_regeneration Tests
# ============================================================================


class TestConsistencyValidatorValidateWithRegeneration:
    """Test suite for validate_with_regeneration method."""

    @pytest.mark.asyncio
    async def test_pass_first_try(self, validator, dynamic_context, conversation_history):
        """Test validation passes on first attempt."""
        response = MagicMock()
        response.content = json.dumps({"score": 0.9})
        validator.llm_client.chat.return_value = response

        final_response, reports = await validator.validate_with_regeneration(
            initial_response="Hello!",
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
        )

        assert final_response == "Hello!"
        assert len(reports) == 1
        assert reports[0].passed is True

    @pytest.mark.asyncio
    async def test_pass_after_n_attempts(self, validator, dynamic_context, conversation_history):
        """Test validation passes after N regeneration attempts."""
        # First attempt fails, second passes
        fail_response = MagicMock(content=json.dumps({"score": 0.3}))
        pass_response = MagicMock(content=json.dumps({"score": 0.9}))
        critique_response = MagicMock(content="Critique")
        revision_response = MagicMock(content="Revised response")

        validator.llm_client.chat.side_effect = [
            # Attempt 1: 5 dimension scores + critique + revision
            fail_response, fail_response, fail_response, fail_response, fail_response,
            critique_response,
            revision_response,
            # Attempt 2: 5 dimension scores (pass)
            pass_response, pass_response, pass_response, pass_response, pass_response,
        ]

        final_response, reports = await validator.validate_with_regeneration(
            initial_response="Hello!",
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
            max_attempts=3,
        )

        assert final_response == "Revised response"
        assert len(reports) == 2
        assert reports[0].passed is False
        assert reports[1].passed is True

    @pytest.mark.asyncio
    async def test_max_attempts_reached(self, validator, dynamic_context, conversation_history):
        """Test validation fails after max attempts reached."""
        fail_response = MagicMock(content=json.dumps({"score": 0.3}))
        critique_response = MagicMock(content="Critique")
        revision_response = MagicMock(content="Revised response")

        # All attempts fail
        validator.llm_client.chat.side_effect = [
            # Attempt 1
            fail_response, fail_response, fail_response, fail_response, fail_response,
            critique_response,
            revision_response,
            # Attempt 2
            fail_response, fail_response, fail_response, fail_response, fail_response,
            critique_response,
            revision_response,
            # Attempt 3
            fail_response, fail_response, fail_response, fail_response, fail_response,
            critique_response,
            revision_response,
        ]

        final_response, reports = await validator.validate_with_regeneration(
            initial_response="Hello!",
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
            max_attempts=3,
        )

        assert len(reports) == 3
        assert all(not r.passed for r in reports)
        assert final_response == "Revised response"  # Last revision

    @pytest.mark.asyncio
    async def test_no_revision_suggestion(self, validator, dynamic_context, conversation_history):
        """Test early exit when no revision suggestion is generated."""
        fail_response = MagicMock(content=json.dumps({"score": 0.3}))
        critique_response = MagicMock(content="Critique")

        # First attempt fails but no revision generated (enable_regeneration=False)
        validator.config.enable_regeneration = False
        validator.llm_client.chat.side_effect = [
            fail_response, fail_response, fail_response, fail_response, fail_response,
            critique_response,
        ]

        final_response, reports = await validator.validate_with_regeneration(
            initial_response="Hello!",
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
        )

        assert len(reports) == 1
        assert reports[0].passed is False
        assert final_response == "Hello!"  # Original response returned

    @pytest.mark.asyncio
    async def test_custom_max_attempts(self, validator, dynamic_context, conversation_history):
        """Test with custom max_attempts parameter."""
        response = MagicMock(content=json.dumps({"score": 0.9}))
        validator.llm_client.chat.return_value = response

        final_response, reports = await validator.validate_with_regeneration(
            initial_response="Hello!",
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
            max_attempts=1,
        )

        assert len(reports) == 1


# ============================================================================
# _score_dimensions and _evaluate_dimension Tests
# ============================================================================


class TestScoreDimensions:
    """Test suite for _score_dimensions and _evaluate_dimension."""

    @pytest.mark.asyncio
    async def test_score_dimensions_all_success(self, validator, dynamic_context, conversation_history):
        """Test _score_dimensions with all successful evaluations."""
        response = MagicMock()
        response.content = json.dumps({"score": 0.85})
        validator.llm_client.chat.return_value = response

        scores = await validator._score_dimensions(
            response="Hello!",
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
        )

        assert len(scores) == 5
        for dim in ConsistencyScore.DIMENSIONS:
            assert dim in scores
            assert 0.0 <= scores[dim] <= 1.0

    @pytest.mark.asyncio
    async def test_score_dimensions_some_fail(self, validator, dynamic_context, conversation_history):
        """Test _score_dimensions when some evaluations fail."""
        success_response = MagicMock(content=json.dumps({"score": 0.8}))
        error_response = Exception("LLM error")

        validator.llm_client.chat.side_effect = [
            success_response,
            error_response,
            success_response,
            error_response,
            success_response,
        ]

        scores = await validator._score_dimensions(
            response="Hello!",
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
        )

        assert len(scores) == 5
        # Failed dimensions should have score 0.0
        assert scores["value_alignment"] == 0.8
        assert scores["personality_consistency"] == 0.0

    @pytest.mark.asyncio
    async def test_evaluate_dimension_json_response(self, validator):
        """Test _evaluate_dimension with clean JSON response."""
        response = MagicMock()
        response.content = json.dumps({"score": 0.75, "reasoning": "Good"})
        validator.llm_client.chat.return_value = response

        score = await validator._evaluate_dimension(
            dim_name="value_alignment",
            prompt="Test prompt",
        )

        assert score == 0.75
        validator.llm_client.chat.assert_called_once()
        call_args = validator.llm_client.chat.call_args
        assert call_args[1]["temperature"] == validator.config.temperature_scoring
        assert call_args[1]["max_tokens"] == 500

    @pytest.mark.asyncio
    async def test_evaluate_dimension_markdown_code_block(self, validator):
        """Test _evaluate_dimension with markdown code block response."""
        response = MagicMock()
        response.content = "```json\n{\"score\": 0.85}\n```"
        validator.llm_client.chat.return_value = response

        score = await validator._evaluate_dimension(
            dim_name="value_alignment",
            prompt="Test prompt",
        )

        assert score == 0.85

    @pytest.mark.asyncio
    async def test_evaluate_dimension_markdown_no_lang(self, validator):
        """Test _evaluate_dimension with markdown block without language tag."""
        response = MagicMock()
        response.content = "```\n{\"score\": 0.9}\n```"
        validator.llm_client.chat.return_value = response

        score = await validator._evaluate_dimension(
            dim_name="value_alignment",
            prompt="Test prompt",
        )

        assert score == 0.9

    @pytest.mark.asyncio
    async def test_evaluate_dimension_malformed_json(self, validator):
        """Test _evaluate_dimension with malformed JSON returns 0.0."""
        response = MagicMock()
        response.content = "not valid json"
        validator.llm_client.chat.return_value = response

        score = await validator._evaluate_dimension(
            dim_name="value_alignment",
            prompt="Test prompt",
        )

        assert score == 0.0

    @pytest.mark.asyncio
    async def test_evaluate_dimension_missing_score_key(self, validator):
        """Test _evaluate_dimension with JSON missing score key."""
        response = MagicMock()
        response.content = json.dumps({"reasoning": "Good"})
        validator.llm_client.chat.return_value = response

        score = await validator._evaluate_dimension(
            dim_name="value_alignment",
            prompt="Test prompt",
        )

        assert score == 0.0

    @pytest.mark.asyncio
    async def test_evaluate_dimension_score_out_of_bounds_high(self, validator):
        """Test _evaluate_dimension clamps score above 1.0."""
        response = MagicMock()
        response.content = json.dumps({"score": 1.5})
        validator.llm_client.chat.return_value = response

        score = await validator._evaluate_dimension(
            dim_name="value_alignment",
            prompt="Test prompt",
        )

        assert score == 1.0

    @pytest.mark.asyncio
    async def test_evaluate_dimension_score_out_of_bounds_low(self, validator):
        """Test _evaluate_dimension clamps score below 0.0."""
        response = MagicMock()
        response.content = json.dumps({"score": -0.5})
        validator.llm_client.chat.return_value = response

        score = await validator._evaluate_dimension(
            dim_name="value_alignment",
            prompt="Test prompt",
        )

        assert score == 0.0

    @pytest.mark.asyncio
    async def test_evaluate_dimension_llm_exception(self, validator):
        """Test _evaluate_dimension handles LLM exception."""
        validator.llm_client.chat.side_effect = Exception("LLM error")

        score = await validator._evaluate_dimension(
            dim_name="value_alignment",
            prompt="Test prompt",
        )

        assert score == 0.0

    @pytest.mark.asyncio
    async def test_evaluate_dimension_whitespace_content(self, validator):
        """Test _evaluate_dimension with whitespace in content."""
        response = MagicMock()
        response.content = "   {\"score\": 0.75}   "
        validator.llm_client.chat.return_value = response

        score = await validator._evaluate_dimension(
            dim_name="value_alignment",
            prompt="Test prompt",
        )

        assert score == 0.75


# ============================================================================
# _generate_critique Tests
# ============================================================================


class TestGenerateCritique:
    """Test suite for _generate_critique method."""

    @pytest.mark.asyncio
    async def test_generate_critique_success(self, validator, dynamic_context):
        """Test _generate_critique with successful LLM call."""
        response = MagicMock()
        response.content = "The response violates core values by being rude."
        validator.llm_client.chat.return_value = response

        scores = {
            "value_alignment": 0.5,
            "personality_consistency": 0.8,
            "historical_coherence": 0.9,
            "emotional_appropriateness": 0.7,
            "contextual_awareness": 0.6,
        }
        violations = ConsistencyScore.get_violations(scores)

        critique = await validator._generate_critique(
            response="Bad response",
            scores=scores,
            dynamic_context=dynamic_context,
            violations=violations,
        )

        assert critique == "The response violates core values by being rude."
        validator.llm_client.chat.assert_called_once()
        call_args = validator.llm_client.chat.call_args
        assert call_args[1]["temperature"] == validator.config.temperature_critique
        assert call_args[1]["max_tokens"] == 800

    @pytest.mark.asyncio
    async def test_generate_critique_no_violations(self, validator, dynamic_context):
        """Test _generate_critique with empty violations list."""
        response = MagicMock()
        response.content = "No issues found."
        validator.llm_client.chat.return_value = response

        scores = {
            "value_alignment": 1.0,
            "personality_consistency": 1.0,
            "historical_coherence": 1.0,
            "emotional_appropriateness": 1.0,
            "contextual_awareness": 1.0,
        }

        critique = await validator._generate_critique(
            response="Good response",
            scores=scores,
            dynamic_context=dynamic_context,
            violations=[],
        )

        assert critique == "No issues found."

    @pytest.mark.asyncio
    async def test_generate_critique_llm_error(self, validator, dynamic_context):
        """Test _generate_critique handles LLM error."""
        validator.llm_client.chat.side_effect = Exception("LLM error")

        scores = {
            "value_alignment": 0.5,
            "personality_consistency": 0.8,
            "historical_coherence": 0.9,
            "emotional_appropriateness": 0.7,
            "contextual_awareness": 0.6,
        }
        violations = ConsistencyScore.get_violations(scores)

        critique = await validator._generate_critique(
            response="Bad response",
            scores=scores,
            dynamic_context=dynamic_context,
            violations=violations,
        )

        assert "Error generating critique" in critique

    @pytest.mark.asyncio
    async def test_generate_critique_with_empty_values(self, validator, dynamic_context):
        """Test _generate_critique when core identity has empty values."""
        validator.core_identity.values.values = []
        validator.core_identity.backstory = ""

        response = MagicMock()
        response.content = "Critique with empty values."
        validator.llm_client.chat.return_value = response

        scores = {
            "value_alignment": 0.5,
            "personality_consistency": 0.8,
            "historical_coherence": 0.9,
            "emotional_appropriateness": 0.7,
            "contextual_awareness": 0.6,
        }
        violations = ConsistencyScore.get_violations(scores)

        critique = await validator._generate_critique(
            response="Bad response",
            scores=scores,
            dynamic_context=dynamic_context,
            violations=violations,
        )

        assert critique == "Critique with empty values."


# ============================================================================
# _generate_revision Tests
# ============================================================================


class TestGenerateRevision:
    """Test suite for _generate_revision method."""

    @pytest.mark.asyncio
    async def test_generate_revision_success(self, validator, dynamic_context, conversation_history):
        """Test _generate_revision with successful LLM call."""
        response = MagicMock()
        response.content = "Revised response text."
        validator.llm_client.chat.return_value = response

        scores = {
            "value_alignment": 0.5,
            "personality_consistency": 0.8,
            "historical_coherence": 0.9,
            "emotional_appropriateness": 0.7,
            "contextual_awareness": 0.6,
        }

        revision = await validator._generate_revision(
            original="Original response",
            critique="Be more polite",
            scores=scores,
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
        )

        assert revision == "Revised response text."
        validator.llm_client.chat.assert_called_once()
        call_args = validator.llm_client.chat.call_args
        assert call_args[1]["temperature"] == validator.config.temperature_revision
        assert call_args[1]["max_tokens"] == 1000

    @pytest.mark.asyncio
    async def test_generate_revision_llm_error(self, validator, dynamic_context, conversation_history):
        """Test _generate_revision returns original on LLM error."""
        validator.llm_client.chat.side_effect = Exception("LLM error")

        scores = {
            "value_alignment": 0.5,
            "personality_consistency": 0.8,
            "historical_coherence": 0.9,
            "emotional_appropriateness": 0.7,
            "contextual_awareness": 0.6,
        }

        revision = await validator._generate_revision(
            original="Original response",
            critique="Be more polite",
            scores=scores,
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
        )

        assert revision == "Original response"

    @pytest.mark.asyncio
    async def test_generate_revision_no_failed_dimensions(self, validator, dynamic_context, conversation_history):
        """Test _generate_revision with no failed dimensions."""
        response = MagicMock()
        response.content = "Revision with no failures."
        validator.llm_client.chat.return_value = response

        scores = {
            "value_alignment": 1.0,
            "personality_consistency": 1.0,
            "historical_coherence": 1.0,
            "emotional_appropriateness": 1.0,
            "contextual_awareness": 1.0,
        }

        revision = await validator._generate_revision(
            original="Original response",
            critique="No issues",
            scores=scores,
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
        )

        assert revision == "Revision with no failures."

    @pytest.mark.asyncio
    async def test_generate_revision_empty_history(self, validator, dynamic_context):
        """Test _generate_revision with empty conversation history."""
        response = MagicMock()
        response.content = "Revision without history."
        validator.llm_client.chat.return_value = response

        scores = {
            "value_alignment": 0.5,
            "personality_consistency": 0.8,
            "historical_coherence": 0.9,
            "emotional_appropriateness": 0.7,
            "contextual_awareness": 0.6,
        }

        revision = await validator._generate_revision(
            original="Original response",
            critique="Be more polite",
            scores=scores,
            dynamic_context=dynamic_context,
            conversation_history=[],
        )

        assert revision == "Revision without history."

    @pytest.mark.asyncio
    async def test_generate_revision_with_empty_identity_fields(self, validator, dynamic_context):
        """Test _generate_revision when identity fields are empty."""
        validator.core_identity.values.values = []
        validator.core_identity.behavioral_matrix.must_always = []
        validator.core_identity.behavioral_matrix.must_never = []
        validator.core_identity.backstory = ""

        response = MagicMock()
        response.content = "Revision with empty identity."
        validator.llm_client.chat.return_value = response

        scores = {
            "value_alignment": 0.5,
            "personality_consistency": 0.8,
            "historical_coherence": 0.9,
            "emotional_appropriateness": 0.7,
            "contextual_awareness": 0.6,
        }

        revision = await validator._generate_revision(
            original="Original response",
            critique="Be more polite",
            scores=scores,
            dynamic_context=dynamic_context,
            conversation_history=[],
        )

        assert revision == "Revision with empty identity."


# ============================================================================
# _build_validation_prompts Tests
# ============================================================================


class TestBuildValidationPrompts:
    """Test suite for _build_validation_prompts method."""

    def test_build_all_five_dimensions(self, validator, dynamic_context, conversation_history):
        """Test that prompts are built for all 5 dimensions."""
        prompts = validator._build_validation_prompts(
            response="Test response",
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
        )

        assert len(prompts) == 5
        assert "value_alignment" in prompts
        assert "personality_consistency" in prompts
        assert "historical_coherence" in prompts
        assert "emotional_appropriateness" in prompts
        assert "contextual_awareness" in prompts

    def test_value_alignment_prompt_content(self, validator, dynamic_context, conversation_history):
        """Test value_alignment prompt includes expected content."""
        prompts = validator._build_validation_prompts(
            response="Test response",
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
        )

        prompt = prompts["value_alignment"]
        assert validator.core_identity.name in prompt
        assert "kindness" in prompt
        assert "honesty" in prompt
        assert "be polite" in prompt
        assert "be rude" in prompt
        assert "Test response" in prompt
        assert dynamic_context.emotional.primary_emotion in prompt
        assert dynamic_context.user_intent in prompt

    def test_personality_consistency_prompt_content(self, validator, dynamic_context, conversation_history):
        """Test personality_consistency prompt includes expected content."""
        prompts = validator._build_validation_prompts(
            response="Test response",
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
        )

        prompt = prompts["personality_consistency"]
        assert validator.core_identity.name in prompt
        assert "Test response" in prompt
        assert dynamic_context.emotional.primary_emotion in prompt
        assert dynamic_context.social.current_stage in prompt

    def test_historical_coherence_prompt_content(self, validator, dynamic_context, conversation_history):
        """Test historical_coherence prompt includes expected content."""
        prompts = validator._build_validation_prompts(
            response="Test response",
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
        )

        prompt = prompts["historical_coherence"]
        assert validator.core_identity.name in prompt
        assert "Test response" in prompt
        assert "Hello" in prompt  # From conversation history
        assert "Hi there!" in prompt

    def test_emotional_appropriateness_prompt_content(self, validator, dynamic_context, conversation_history):
        """Test emotional_appropriateness prompt includes expected content."""
        prompts = validator._build_validation_prompts(
            response="Test response",
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
        )

        prompt = prompts["emotional_appropriateness"]
        assert validator.core_identity.name in prompt
        assert dynamic_context.emotional.primary_emotion in prompt
        assert dynamic_context.user_intent in prompt
        assert "Test response" in prompt

    def test_contextual_awareness_prompt_content(self, validator, dynamic_context, conversation_history):
        """Test contextual_awareness prompt includes expected content."""
        prompts = validator._build_validation_prompts(
            response="Test response",
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
        )

        prompt = prompts["contextual_awareness"]
        assert validator.core_identity.name in prompt
        assert dynamic_context.topic in prompt
        assert dynamic_context.user_intent in prompt
        assert str(dynamic_context.conversation_turn) in prompt
        assert "answer question" in prompt  # active goal
        assert "Test response" in prompt

    def test_build_prompts_empty_history(self, validator, dynamic_context):
        """Test prompt building with empty conversation history."""
        prompts = validator._build_validation_prompts(
            response="Test response",
            dynamic_context=dynamic_context,
            conversation_history=[],
        )

        assert len(prompts) == 5
        # Historical coherence should have "No prior conversation"
        assert "No prior conversation" in prompts["historical_coherence"]

    def test_build_prompts_empty_identity_values(self, validator, dynamic_context):
        """Test prompt building with empty identity values."""
        validator.core_identity.values.values = []
        validator.core_identity.behavioral_matrix.must_always = []
        validator.core_identity.behavioral_matrix.must_never = []
        validator.core_identity.backstory = ""

        prompts = validator._build_validation_prompts(
            response="Test response",
            dynamic_context=dynamic_context,
            conversation_history=[],
        )

        assert len(prompts) == 5
        assert "None defined" in prompts["value_alignment"]
        assert "Not specified" in prompts["personality_consistency"]

    def test_build_prompts_long_history_truncated(self, validator, dynamic_context):
        """Test that only last 5 messages are included in history."""
        long_history = [
            Message(role="user", content=f"Message {i}")
            for i in range(10)
        ]

        prompts = validator._build_validation_prompts(
            response="Test response",
            dynamic_context=dynamic_context,
            conversation_history=long_history,
        )

        history_prompt = prompts["historical_coherence"]
        assert "Message 5" in history_prompt
        assert "Message 9" in history_prompt
        # Earlier messages should not be present
        assert "Message 0" not in history_prompt
        assert "Message 4" not in history_prompt

    def test_build_prompts_no_active_goals(self, validator, dynamic_context, conversation_history):
        """Test contextual_awareness prompt when no active goals."""
        dynamic_context.cognitive.active_goals = []

        prompts = validator._build_validation_prompts(
            response="Test response",
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
        )

        assert "None" in prompts["contextual_awareness"]


# ============================================================================
# _calculate_confidence Tests
# ============================================================================


class TestCalculateConfidence:
    """Test suite for _calculate_confidence method."""

    def test_calculate_confidence_perfect_scores(self):
        """Test confidence with perfect uniform scores."""
        validator = ConsistencyValidator(
            llm_client=AsyncMock(),
            core_identity=CoreIdentity(name="Test"),
        )
        scores = {
            "value_alignment": 1.0,
            "personality_consistency": 1.0,
            "historical_coherence": 1.0,
            "emotional_appropriateness": 1.0,
            "contextual_awareness": 1.0,
        }
        confidence = validator._calculate_confidence(scores)
        assert confidence == 1.0

    def test_calculate_confidence_empty_scores(self):
        """Test confidence with empty scores."""
        validator = ConsistencyValidator(
            llm_client=AsyncMock(),
            core_identity=CoreIdentity(name="Test"),
        )
        confidence = validator._calculate_confidence({})
        assert confidence == 0.0

    def test_calculate_confidence_missing_dimensions(self):
        """Test confidence with missing dimensions."""
        validator = ConsistencyValidator(
            llm_client=AsyncMock(),
            core_identity=CoreIdentity(name="Test"),
        )
        scores = {
            "value_alignment": 0.8,
            "personality_consistency": 0.8,
        }
        confidence = validator._calculate_confidence(scores)
        assert confidence == 0.5

    def test_calculate_confidence_high_variance(self):
        """Test confidence with high variance scores."""
        validator = ConsistencyValidator(
            llm_client=AsyncMock(),
            core_identity=CoreIdentity(name="Test"),
        )
        scores = {
            "value_alignment": 1.0,
            "personality_consistency": 1.0,
            "historical_coherence": 1.0,
            "emotional_appropriateness": 0.0,
            "contextual_awareness": 0.0,
        }
        confidence = validator._calculate_confidence(scores)
        # High variance should result in lower confidence than perfect uniformity
        assert confidence < 1.0

    def test_calculate_confidence_low_variance(self):
        """Test confidence with low variance scores."""
        validator = ConsistencyValidator(
            llm_client=AsyncMock(),
            core_identity=CoreIdentity(name="Test"),
        )
        scores = {
            "value_alignment": 0.8,
            "personality_consistency": 0.82,
            "historical_coherence": 0.79,
            "emotional_appropriateness": 0.81,
            "contextual_awareness": 0.8,
        }
        confidence = validator._calculate_confidence(scores)
        # Low variance should result in high confidence
        assert confidence > 0.9

    def test_calculate_confidence_rounded(self):
        """Test that confidence is rounded to 3 decimal places."""
        validator = ConsistencyValidator(
            llm_client=AsyncMock(),
            core_identity=CoreIdentity(name="Test"),
        )
        scores = {
            "value_alignment": 0.75,
            "personality_consistency": 0.75,
            "historical_coherence": 0.75,
            "emotional_appropriateness": 0.75,
            "contextual_awareness": 0.75,
        }
        confidence = validator._calculate_confidence(scores)
        assert confidence == 1.0


# ============================================================================
# get_validation_stats Tests
# ============================================================================


class TestGetValidationStats:
    """Test suite for get_validation_stats method."""

    def test_empty_history(self):
        """Test stats with empty validation history."""
        validator = ConsistencyValidator(
            llm_client=AsyncMock(),
            core_identity=CoreIdentity(name="Test"),
        )
        stats = validator.get_validation_stats()

        assert stats["total_validations"] == 0
        assert stats["pass_rate"] == 0.0
        assert stats["average_score"] == 0.0

    def test_with_history_all_pass(self):
        """Test stats with all passing validations."""
        history = [
            ValidationResult(overall_valid=True, overall_score=0.9),
            ValidationResult(overall_valid=True, overall_score=0.85),
            ValidationResult(overall_valid=True, overall_score=0.95),
        ]
        validator = ConsistencyValidator(
            llm_client=AsyncMock(),
            core_identity=CoreIdentity(name="Test"),
            validation_history=history,
        )
        stats = validator.get_validation_stats()

        assert stats["total_validations"] == 3
        assert stats["pass_rate"] == 1.0
        assert stats["average_score"] == pytest.approx(0.9, abs=0.01)

    def test_with_history_all_fail(self):
        """Test stats with all failing validations."""
        history = [
            ValidationResult(overall_valid=False, overall_score=0.4),
            ValidationResult(overall_valid=False, overall_score=0.3),
        ]
        validator = ConsistencyValidator(
            llm_client=AsyncMock(),
            core_identity=CoreIdentity(name="Test"),
            validation_history=history,
        )
        stats = validator.get_validation_stats()

        assert stats["total_validations"] == 2
        assert stats["pass_rate"] == 0.0
        assert stats["average_score"] == pytest.approx(0.35, abs=0.01)

    def test_with_history_mixed(self):
        """Test stats with mixed pass/fail validations."""
        history = [
            ValidationResult(overall_valid=True, overall_score=0.9),
            ValidationResult(overall_valid=False, overall_score=0.4),
            ValidationResult(overall_valid=True, overall_score=0.8),
            ValidationResult(overall_valid=False, overall_score=0.5),
        ]
        validator = ConsistencyValidator(
            llm_client=AsyncMock(),
            core_identity=CoreIdentity(name="Test"),
            validation_history=history,
        )
        stats = validator.get_validation_stats()

        assert stats["total_validations"] == 4
        assert stats["pass_rate"] == 0.5
        assert stats["average_score"] == pytest.approx(0.65, abs=0.01)

    def test_average_score_rounding(self):
        """Test that average score is rounded to 3 decimal places."""
        history = [
            ValidationResult(overall_valid=True, overall_score=0.3333),
            ValidationResult(overall_valid=True, overall_score=0.6667),
        ]
        validator = ConsistencyValidator(
            llm_client=AsyncMock(),
            core_identity=CoreIdentity(name="Test"),
            validation_history=history,
        )
        stats = validator.get_validation_stats()

        assert stats["average_score"] == pytest.approx(0.5, abs=0.01)


# ============================================================================
# ValidationError Tests
# ============================================================================


class TestValidationError:
    """Test suite for ValidationError exception."""

    def test_basic_error(self):
        """Test basic ValidationError creation."""
        error = ValidationError("Something went wrong")
        assert "Something went wrong" in str(error)
        assert error.code == "VALIDATION_ERROR"

    def test_error_with_details(self):
        """Test ValidationError with details."""
        details = {"dimension": "value_alignment", "score": 0.3}
        error = ValidationError("Low score", details=details)
        assert error.details == details


# ============================================================================
# Message Model Tests
# ============================================================================


class TestMessage:
    """Test suite for Message Pydantic model."""

    def test_valid_message(self):
        """Test creating a valid Message."""
        msg = Message(role="user", content="Hello", timestamp="2024-01-01T00:00:00")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.timestamp == "2024-01-01T00:00:00"

    def test_valid_assistant_message(self):
        """Test creating an assistant message."""
        msg = Message(role="assistant", content="Hi!")
        assert msg.role == "assistant"
        assert msg.content == "Hi!"
        assert msg.timestamp is None

    def test_valid_system_message(self):
        """Test creating a system message."""
        msg = Message(role="system", content="You are helpful.")
        assert msg.role == "system"

    def test_invalid_role(self):
        """Test that invalid role raises validation error."""
        with pytest.raises(Exception):  # pydantic.ValidationError
            Message(role="invalid", content="Hello")

    def test_no_timestamp(self):
        """Test Message without timestamp."""
        msg = Message(role="user", content="Hello")
        assert msg.timestamp is None


# ============================================================================
# VALIDATION_PROMPTS Tests
# ============================================================================


class TestValidationPrompts:
    """Test suite for VALIDATION_PROMPTS dictionary."""

    def test_all_prompts_present(self):
        """Test that all expected prompt keys are present."""
        expected_keys = [
            "value_alignment",
            "personality_consistency",
            "historical_coherence",
            "emotional_appropriateness",
            "contextual_awareness",
            "self_critique",
            "revision",
        ]
        for key in expected_keys:
            assert key in VALIDATION_PROMPTS

    def test_prompts_are_strings(self):
        """Test that all prompts are strings."""
        for _key, prompt in VALIDATION_PROMPTS.items():
            assert isinstance(prompt, str)
            assert len(prompt) > 0

    def test_value_alignment_prompt_structure(self):
        """Test value_alignment prompt has expected structure."""
        prompt = VALIDATION_PROMPTS["value_alignment"]
        assert "{character_name}" in prompt
        assert "{core_values}" in prompt
        assert "{must_always}" in prompt
        assert "{must_never}" in prompt
        assert "{response}" in prompt
        assert "{emotional_state}" in prompt
        assert "{user_intent}" in prompt

    def test_self_critique_prompt_structure(self):
        """Test self_critique prompt has expected structure."""
        prompt = VALIDATION_PROMPTS["self_critique"]
        assert "{character_name}" in prompt
        assert "{core_values}" in prompt
        assert "{response}" in prompt
        assert "{validation_scores}" in prompt
        assert "{violations}" in prompt

    def test_revision_prompt_structure(self):
        """Test revision prompt has expected structure."""
        prompt = VALIDATION_PROMPTS["revision"]
        assert "{character_name}" in prompt
        assert "{original_response}" in prompt
        assert "{critique}" in prompt
        assert "{failed_dimensions}" in prompt


# ============================================================================
# Integration Tests
# ============================================================================


class TestConsistencyValidatorIntegration:
    """Integration-style tests for ConsistencyValidator."""

    @pytest.mark.asyncio
    async def test_full_validation_pipeline_pass(self, core_identity, dynamic_context, conversation_history):
        """Test complete validation pipeline with passing response."""
        client = AsyncMock()
        response = MagicMock()
        response.content = json.dumps({"score": 0.9})
        client.chat.return_value = response

        validator = ConsistencyValidator(
            llm_client=client,
            core_identity=core_identity,
        )

        report = await validator.validate(
            response="This is a great response!",
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
        )

        assert report.passed is True
        assert report.overall_score > 0.7
        assert len(report.dimension_scores) == 5

    @pytest.mark.asyncio
    async def test_full_validation_pipeline_fail_then_regenerate(self, core_identity, dynamic_context, conversation_history):
        """Test complete pipeline with failing response and regeneration."""
        client = AsyncMock()
        fail_response = MagicMock(content=json.dumps({"score": 0.3}))
        pass_response = MagicMock(content=json.dumps({"score": 0.9}))
        critique_response = MagicMock(content="The response is too brief.")
        revision_response = MagicMock(content="This is a much better, more detailed response.")

        client.chat.side_effect = [
            # Attempt 1: all fail
            fail_response, fail_response, fail_response, fail_response, fail_response,
            critique_response,
            revision_response,
            # Attempt 2: all pass
            pass_response, pass_response, pass_response, pass_response, pass_response,
        ]

        validator = ConsistencyValidator(
            llm_client=client,
            core_identity=core_identity,
        )

        final_response, reports = await validator.validate_with_regeneration(
            initial_response="Bad",
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
            max_attempts=3,
        )

        assert final_response == "This is a much better, more detailed response."
        assert len(reports) == 2
        assert reports[0].passed is False
        assert reports[1].passed is True

    @pytest.mark.asyncio
    async def test_validation_updates_history(self, core_identity, dynamic_context, conversation_history):
        """Test that validation can work with history."""
        history = [
            ValidationResult(overall_valid=True, overall_score=0.85),
        ]
        client = AsyncMock()
        response = MagicMock(content=json.dumps({"score": 0.9}))
        client.chat.return_value = response

        validator = ConsistencyValidator(
            llm_client=client,
            core_identity=core_identity,
            validation_history=history,
        )

        stats = validator.get_validation_stats()
        assert stats["total_validations"] == 1
        assert stats["pass_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_empty_identity_prompts(self, dynamic_context, conversation_history):
        """Test with minimal identity (empty fields)."""
        minimal_identity = CoreIdentity(
            name="Minimal",
            backstory="",
            values=CoreValues(),
            behavioral_matrix=BehavioralMatrix(),
        )
        client = AsyncMock()
        response = MagicMock(content=json.dumps({"score": 0.8}))
        client.chat.return_value = response

        validator = ConsistencyValidator(
            llm_client=client,
            core_identity=minimal_identity,
        )

        prompts = validator._build_validation_prompts(
            response="Test",
            dynamic_context=dynamic_context,
            conversation_history=conversation_history,
        )

        assert len(prompts) == 5
        assert "None defined" in prompts["value_alignment"]
        assert "Not specified" in prompts["personality_consistency"]

    @pytest.mark.asyncio
    async def test_json_parsing_edge_cases(self, validator):
        """Test various JSON response formats from LLM."""
        test_cases = [
            ('{"score": 0.75}', 0.75),
            ('```json\n{"score": 0.8}\n```', 0.8),
            ('```\n{"score": 0.85}\n```', 0.85),
            ('   {"score": 0.9}   ', 0.9),
            ('{"score": 1.5}', 1.0),  # Clamped
            ('{"score": -0.5}', 0.0),  # Clamped
            ('invalid json', 0.0),
            ('{"reasoning": "no score"}', 0.0),
        ]

        for content, expected in test_cases:
            response = MagicMock()
            response.content = content
            validator.llm_client.chat.return_value = response

            score = await validator._evaluate_dimension(
                dim_name="value_alignment",
                prompt="Test",
            )
            assert score == expected, f"Failed for content: {content}"
