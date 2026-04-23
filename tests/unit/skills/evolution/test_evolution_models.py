"""Unit tests for skill evolution models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from persona_agent.skills.evolution.models import (
    EvolutionConfig,
    EvolutionMode,
    EvolutionProposal,
    ProposalStatus,
    SkillExecution,
    SkillMetrics,
)


class TestEvolutionMode:
    """Tests for EvolutionMode enum."""

    def test_mode_values(self):
        """Test mode string values."""
        assert EvolutionMode.FIX.value == "fix"
        assert EvolutionMode.DERIVED.value == "derived"
        assert EvolutionMode.CAPTURED.value == "captured"

    def test_from_string_valid(self):
        """Test creating mode from valid string."""
        assert EvolutionMode.from_string("fix") == EvolutionMode.FIX
        assert EvolutionMode.from_string("FIX") == EvolutionMode.FIX
        assert EvolutionMode.from_string("derived") == EvolutionMode.DERIVED

    def test_from_string_invalid(self):
        """Test creating mode from invalid string."""
        with pytest.raises(ValueError, match="Invalid evolution mode"):
            EvolutionMode.from_string("invalid")


class TestSkillExecution:
    """Tests for SkillExecution dataclass."""

    def test_creation(self):
        """Test basic creation."""
        execution = SkillExecution(
            skill_name="test_skill",
            timestamp=datetime.now(UTC),
            input_summary="Test input",
            success=True,
            execution_time_ms=150,
        )

        assert execution.skill_name == "test_skill"
        assert execution.success is True
        assert execution.execution_time_ms == 150

    def test_create_factory(self):
        """Test create factory method."""
        execution = SkillExecution.create(
            skill_name="test_skill",
            input_summary="Test input",
            success=True,
            execution_time_ms=150,
            user_feedback="Good job",
        )

        assert execution.skill_name == "test_skill"
        assert execution.user_feedback == "Good job"
        assert execution.timestamp.tzinfo is not None

    def test_to_dict(self):
        """Test serialization."""
        execution = SkillExecution.create(
            skill_name="test_skill",
            input_summary="Test",
            success=True,
        )

        data = execution.to_dict()

        assert data["skill_name"] == "test_skill"
        assert data["success"] is True
        assert "timestamp" in data


class TestSkillMetrics:
    """Tests for SkillMetrics."""

    def test_initial_state(self):
        """Test initial metrics state."""
        metrics = SkillMetrics(skill_name="test_skill")

        assert metrics.total_executions == 0
        assert metrics.success_rate == 0.0
        assert not metrics.needs_improvement

    def test_record_execution_success(self):
        """Test recording successful execution."""
        metrics = SkillMetrics(skill_name="test_skill")

        execution = SkillExecution.create(
            skill_name="test_skill",
            input_summary="Test",
            success=True,
            execution_time_ms=100,
        )

        metrics.record_execution(execution)

        assert metrics.total_executions == 1
        assert metrics.successful_executions == 1
        assert metrics.success_rate == 1.0

    def test_record_execution_failure(self):
        """Test recording failed execution."""
        metrics = SkillMetrics(skill_name="test_skill")

        execution = SkillExecution.create(
            skill_name="test_skill",
            input_summary="Test",
            success=False,
            error_message="Connection error",
        )

        metrics.record_execution(execution)

        assert metrics.total_executions == 1
        assert metrics.failed_executions == 1
        assert metrics.success_rate == 0.0
        assert "Connection error" in metrics.common_errors

    def test_needs_improvement_low_success(self):
        """Test detection of skills needing improvement."""
        metrics = SkillMetrics(skill_name="test_skill")

        # Add 5 failed executions
        for i in range(5):
            metrics.record_execution(
                SkillExecution.create(
                    skill_name="test_skill",
                    input_summary=f"Test {i}",
                    success=False,
                    error_message=f"Error {i}",
                )
            )

        assert metrics.needs_improvement

    def test_is_performing_well(self):
        """Test detection of well-performing skills."""
        metrics = SkillMetrics(skill_name="test_skill")

        # Add 10 successful executions
        for i in range(10):
            metrics.record_execution(
                SkillExecution.create(
                    skill_name="test_skill",
                    input_summary=f"Test {i}",
                    success=True,
                )
            )

        assert metrics.is_performing_well

    def test_get_recent_errors(self):
        """Test getting recent errors."""
        metrics = SkillMetrics(skill_name="test_skill")

        # Add mixed executions
        for i in range(5):
            metrics.record_execution(
                SkillExecution.create(
                    skill_name="test_skill",
                    input_summary=f"Test {i}",
                    success=i % 2 == 0,
                    error_message=f"Error {i}" if i % 2 else None,
                )
            )

        errors = metrics.get_recent_errors(count=2)
        assert len(errors) == 2

    def test_get_top_errors(self):
        """Test getting most frequent errors."""
        metrics = SkillMetrics(skill_name="test_skill")

        # Add executions with same error
        for _ in range(3):
            metrics.record_execution(
                SkillExecution.create(
                    skill_name="test_skill",
                    input_summary="Test",
                    success=False,
                    error_message="Same error",
                )
            )

        top_errors = metrics.get_top_errors(count=1)
        assert len(top_errors) == 1
        assert top_errors[0] == ("Same error", 3)

    def test_history_size_limit(self):
        """Test that history size is limited."""
        metrics = SkillMetrics(skill_name="test_skill", max_history_size=5)

        # Add more executions than max
        for i in range(10):
            metrics.record_execution(
                SkillExecution.create(
                    skill_name="test_skill",
                    input_summary=f"Test {i}",
                    success=True,
                )
            )

        assert len(metrics.execution_history) == 5


class TestEvolutionProposal:
    """Tests for EvolutionProposal."""

    @pytest.fixture
    def sample_proposal(self):
        """Create a sample proposal."""
        return EvolutionProposal(
            id="prop_001",
            skill_name="test_skill",
            mode=EvolutionMode.FIX,
            original_code="class TestSkill: pass",
            proposed_code="class TestSkillV2: pass",
            reasoning="Fixed bugs",
            created_at=datetime.now(UTC),
        )

    def test_creation(self, sample_proposal):
        """Test proposal creation."""
        assert sample_proposal.id == "prop_001"
        assert sample_proposal.skill_name == "test_skill"
        assert sample_proposal.mode == EvolutionMode.FIX
        assert sample_proposal.is_pending

    def test_approve(self, sample_proposal):
        """Test proposal approval."""
        sample_proposal.approve(reviewed_by="admin")

        assert sample_proposal.status == ProposalStatus.APPROVED
        assert sample_proposal.reviewed_by == "admin"
        assert sample_proposal.reviewed_at is not None

    def test_reject(self, sample_proposal):
        """Test proposal rejection."""
        sample_proposal.reject(reason="Not good enough", reviewed_by="admin")

        assert sample_proposal.status == ProposalStatus.REJECTED
        assert sample_proposal.rejection_reason == "Not good enough"
        assert sample_proposal.reviewed_by == "admin"

    def test_age_hours(self, sample_proposal):
        """Test age calculation."""
        # Created just now, should be ~0 hours
        assert sample_proposal.age_hours < 0.1

        # Modify creation time to be older
        sample_proposal.created_at = datetime.now(UTC) - timedelta(hours=5)
        assert 4.9 < sample_proposal.age_hours < 5.1

    def test_to_dict(self, sample_proposal):
        """Test serialization."""
        data = sample_proposal.to_dict()

        assert data["id"] == "prop_001"
        assert data["skill_name"] == "test_skill"
        assert data["mode"] == "fix"
        assert data["status"] == "pending"
        assert data["is_pending"] is True


class TestEvolutionConfig:
    """Tests for EvolutionConfig."""

    def test_defaults(self):
        """Test default configuration."""
        config = EvolutionConfig()

        assert config.enabled is True
        assert config.min_executions_before_evolution == 5
        assert config.success_rate_threshold == 0.7
        assert config.require_human_approval is True

    def test_validation_min_executions(self):
        """Test validation of min_executions."""
        with pytest.raises(ValueError, match="min_executions"):
            EvolutionConfig(min_executions_before_evolution=1)

    def test_validation_success_rate(self):
        """Test validation of success_rate_threshold."""
        with pytest.raises(ValueError, match="success_rate_threshold"):
            EvolutionConfig(success_rate_threshold=1.5)

        with pytest.raises(ValueError, match="success_rate_threshold"):
            EvolutionConfig(success_rate_threshold=-0.1)

    def test_validation_max_proposals(self):
        """Test validation of max_proposals_per_skill."""
        with pytest.raises(ValueError, match="max_proposals_per_skill"):
            EvolutionConfig(max_proposals_per_skill=0)
