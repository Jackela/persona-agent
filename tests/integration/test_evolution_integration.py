"""Integration tests for the skill evolution system.

Tests skill execution tracking, metrics collection, proposal generation,
and the evolution workflow with real and mocked components.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from persona_agent.skills.base import SkillContext, SkillResult
from persona_agent.skills.evolution import (
    EvolutionConfig,
    EvolutionManager,
    EvolutionMode,
    EvolutionProposal,
    ProposalStatus,
    SkillEvolutionTracker,
)
from persona_agent.skills.evolution.exceptions import ProposalError
from persona_agent.skills.registry import SkillRegistry


@pytest.fixture
def evolution_config():
    """Create an evolution configuration for testing."""
    return EvolutionConfig(
        enabled=True,
        min_executions_before_evolution=3,
        success_rate_threshold=0.7,
        max_proposals_per_skill=2,
        proposal_expiry_hours=24.0,
        storage_path="./test_data/skill_evolution",
    )


@pytest.fixture
def temp_evolution_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for evolution data."""
    evolution_dir = tmp_path / "skill_evolution"
    evolution_dir.mkdir(parents=True)
    return evolution_dir


@pytest.fixture
def mock_skill_class():
    """Create a mock skill class for testing."""

    class MockSkill:
        """A mock skill for testing evolution."""

        name = "mock_skill"
        priority = 1

        def can_handle(self, context):
            return True

        async def execute(self, context):
            return SkillResult(
                success=True,
                response="Mock response",
                confidence=0.9,
            )

    return MockSkill


@pytest.mark.asyncio
class TestSkillEvolutionTrackerIntegration:
    """Test SkillEvolutionTracker integration with skill execution."""

    async def test_tracker_records_successful_execution(self, evolution_config):
        """Test that tracker records successful skill execution."""
        tracker = SkillEvolutionTracker(config=evolution_config)

        context = SkillContext(
            user_input="Test input",
            conversation_history=[],
            current_mood="neutral",
        )
        result = SkillResult(
            success=True,
            response="Success",
            confidence=0.9,
        )

        tracker.record_execution(
            skill_name="test_skill",
            context=context,
            result=result,
            execution_time_ms=100,
        )

        metrics = tracker.get_metrics("test_skill")
        assert metrics is not None
        assert metrics.total_executions == 1
        assert metrics.successful_executions == 1

    async def test_tracker_records_failed_execution(self, evolution_config):
        """Test that tracker records failed skill execution."""
        tracker = SkillEvolutionTracker(config=evolution_config)

        context = SkillContext(
            user_input="Test input",
            conversation_history=[],
            current_mood="neutral",
        )
        result = SkillResult(
            success=False,
            response="",
            confidence=0.0,
            data={"error": "Test error"},
        )

        tracker.record_execution(
            skill_name="failing_skill",
            context=context,
            result=result,
            execution_time_ms=50,
        )

        metrics = tracker.get_metrics("failing_skill")
        assert metrics.total_executions == 1
        assert metrics.failed_executions == 1
        assert metrics.success_rate == 0.0

    async def test_tracker_calculates_success_rate(self, evolution_config):
        """Test that tracker correctly calculates success rate."""
        tracker = SkillEvolutionTracker(config=evolution_config)

        context = SkillContext(
            user_input="Test",
            conversation_history=[],
            current_mood="neutral",
        )

        # 7 successes, 3 failures
        for _ in range(7):
            result = SkillResult(success=True, response="OK")
            tracker.record_execution("mixed_skill", context, result)

        for _ in range(3):
            result = SkillResult(success=False, response="", data={"error": "fail"})
            tracker.record_execution("mixed_skill", context, result)

        metrics = tracker.get_metrics("mixed_skill")
        assert metrics.success_rate == 0.7
        assert metrics.total_executions == 10

    async def test_tracker_tracks_error_patterns(self, evolution_config):
        """Test that tracker tracks different error patterns."""
        tracker = SkillEvolutionTracker(config=evolution_config)

        context = SkillContext(
            user_input="Test",
            conversation_history=[],
            current_mood="neutral",
        )

        # Different errors
        errors = ["Connection timeout", "Invalid API key", "Connection timeout"]
        for error in errors:
            result = SkillResult(
                success=False,
                response="",
                data={"error": error},
            )
            tracker.record_execution("error_skill", context, result)

        metrics = tracker.get_metrics("error_skill")
        top_errors = metrics.get_top_errors()

        assert len(top_errors) == 2  # Two unique errors
        assert top_errors[0][1] == 2  # Connection timeout appears twice

    async def test_needs_evolution_detection(self, evolution_config):
        """Test detection of skills needing evolution."""
        tracker = SkillEvolutionTracker(config=evolution_config)

        context = SkillContext(
            user_input="Test",
            conversation_history=[],
            current_mood="neutral",
        )

        # Skill with low success rate after enough executions (needs 5+ for needs_improvement)
        for _ in range(5):
            result = SkillResult(
                success=False,
                response="",
                data={"error": "Consistent failure"},
            )
            tracker.record_execution("poor_skill", context, result)

        assert tracker.needs_evolution("poor_skill") is True

    async def test_get_skills_needing_evolution(self, evolution_config):
        """Test getting list of skills needing evolution."""
        tracker = SkillEvolutionTracker(config=evolution_config)

        context = SkillContext(
            user_input="Test",
            conversation_history=[],
            current_mood="neutral",
        )

        # One good skill, one bad skill
        for _ in range(5):
            tracker.record_execution(
                "good_skill", context, SkillResult(success=True, response="OK")
            )
            tracker.record_execution(
                "bad_skill", context, SkillResult(success=False, response="", data={"error": "fail"})
            )

        skills_needing_evolution = tracker.get_skills_needing_evolution()

        assert "bad_skill" in skills_needing_evolution
        assert "good_skill" not in skills_needing_evolution

    async def test_recommended_mode_for_low_success(self, evolution_config):
        """Test that FIX mode is recommended for low success rate."""
        tracker = SkillEvolutionTracker(config=evolution_config)

        context = SkillContext(
            user_input="Test",
            conversation_history=[],
            current_mood="neutral",
        )

        # Low success rate
        for _ in range(5):
            tracker.record_execution(
                "failing_skill",
                context,
                SkillResult(success=False, response="", data={"error": "fail"}),
            )

        mode = tracker.get_recommended_mode("failing_skill")
        assert mode == "fix"

    async def test_recommended_mode_for_high_success(self, evolution_config):
        """Test that DERIVED mode is recommended for high success rate."""
        tracker = SkillEvolutionTracker(config=evolution_config)

        context = SkillContext(
            user_input="Test",
            conversation_history=[],
            current_mood="neutral",
        )

        # High success rate with many executions
        for _ in range(15):
            tracker.record_execution(
                "excellent_skill",
                context,
                SkillResult(success=True, response="Great!"),
            )

        mode = tracker.get_recommended_mode("excellent_skill")
        assert mode == "derived"


@pytest.mark.asyncio
class TestEvolutionManagerIntegration:
    """Test EvolutionManager integration with proposal lifecycle."""

    async def test_manager_stores_proposal(self, temp_evolution_dir):
        """Test that manager stores proposals."""
        config = EvolutionConfig(storage_path=str(temp_evolution_dir))
        manager = EvolutionManager(config)

        proposal = EvolutionProposal(
            id="test_proposal_001",
            skill_name="test_skill",
            mode=EvolutionMode.FIX,
            original_code="original",
            proposed_code="proposed",
            reasoning="Test reasoning",
            created_at=datetime.now(UTC),
        )

        await manager.store_proposal(proposal)

        # Should be able to retrieve
        retrieved = await manager.get_proposal("test_proposal_001")
        assert retrieved is not None
        assert retrieved.skill_name == "test_skill"

    async def test_manager_enforces_max_proposals(self, temp_evolution_dir):
        """Test that manager enforces max proposals per skill."""
        config = EvolutionConfig(
            storage_path=str(temp_evolution_dir),
            max_proposals_per_skill=2,
        )
        manager = EvolutionManager(config)

        # Create max proposals
        for i in range(2):
            proposal = EvolutionProposal(
                id=f"proposal_{i}",
                skill_name="limited_skill",
                mode=EvolutionMode.FIX,
                original_code="original",
                proposed_code="proposed",
                reasoning="Test",
                created_at=datetime.now(UTC),
            )
            await manager.store_proposal(proposal)

        # Third proposal should fail
        third = EvolutionProposal(
            id="proposal_3",
            skill_name="limited_skill",
            mode=EvolutionMode.FIX,
            original_code="original",
            proposed_code="proposed",
            reasoning="Test",
            created_at=datetime.now(UTC),
        )

        with pytest.raises(ProposalError):
            await manager.store_proposal(third)

    async def test_manager_approves_proposal(self, temp_evolution_dir):
        """Test that manager can approve proposals."""
        config = EvolutionConfig(storage_path=str(temp_evolution_dir))
        manager = EvolutionManager(config)

        proposal = EvolutionProposal(
            id="approve_test",
            skill_name="test_skill",
            mode=EvolutionMode.FIX,
            original_code="original",
            proposed_code="proposed",
            reasoning="Test",
            created_at=datetime.now(UTC),
        )

        await manager.store_proposal(proposal)

        # Approve
        result = await manager.approve_proposal("approve_test", reviewer="admin")

        assert result is True

        # Check status
        retrieved = await manager.get_proposal("approve_test")
        assert retrieved.status == ProposalStatus.APPROVED
        assert retrieved.reviewed_by == "admin"

    async def test_manager_rejects_proposal(self, temp_evolution_dir):
        """Test that manager can reject proposals."""
        config = EvolutionConfig(storage_path=str(temp_evolution_dir))
        manager = EvolutionManager(config)

        proposal = EvolutionProposal(
            id="reject_test",
            skill_name="test_skill",
            mode=EvolutionMode.FIX,
            original_code="original",
            proposed_code="proposed",
            reasoning="Test",
            created_at=datetime.now(UTC),
        )

        await manager.store_proposal(proposal)

        # Reject
        result = await manager.reject_proposal(
            "reject_test",
            reason="Doesn't meet standards",
            reviewer="admin",
        )

        assert result is True

        # Check status
        retrieved = await manager.get_proposal("reject_test")
        assert retrieved.status == ProposalStatus.REJECTED
        assert retrieved.rejection_reason == "Doesn't meet standards"

    async def test_manager_lists_proposals_by_status(self, temp_evolution_dir):
        """Test listing proposals filtered by status."""
        config = EvolutionConfig(storage_path=str(temp_evolution_dir))
        manager = EvolutionManager(config)

        # Create proposals with different statuses
        pending = EvolutionProposal(
            id="pending_1",
            skill_name="skill_a",
            mode=EvolutionMode.FIX,
            original_code="original",
            proposed_code="proposed",
            reasoning="Test",
            created_at=datetime.now(UTC),
        )
        await manager.store_proposal(pending)

        approved = EvolutionProposal(
            id="approved_1",
            skill_name="skill_b",
            mode=EvolutionMode.FIX,
            original_code="original",
            proposed_code="proposed",
            reasoning="Test",
            created_at=datetime.now(UTC),
        )
        await manager.store_proposal(approved)
        await manager.approve_proposal("approved_1", reviewer="admin")

        # List pending
        pending_list = await manager.list_proposals(status=ProposalStatus.PENDING)
        assert len(pending_list) == 1
        assert pending_list[0].id == "pending_1"

        # List approved
        approved_list = await manager.list_proposals(status=ProposalStatus.APPROVED)
        assert len(approved_list) == 1
        assert approved_list[0].id == "approved_1"

    async def test_manager_gets_statistics(self, temp_evolution_dir):
        """Test getting manager statistics."""
        config = EvolutionConfig(storage_path=str(temp_evolution_dir))
        manager = EvolutionManager(config)

        # Create some proposals
        for i in range(3):
            proposal = EvolutionProposal(
                id=f"stat_{i}",
                skill_name="stat_skill",
                mode=EvolutionMode.FIX,
                original_code="original",
                proposed_code="proposed",
                reasoning="Test",
                created_at=datetime.now(UTC),
            )
            await manager.store_proposal(proposal)

        # Approve one
        await manager.approve_proposal("stat_0", reviewer="admin")

        stats = manager.get_statistics()

        assert stats["total_proposals"] == 3
        assert stats["pending"] == 2
        assert stats["approved"] == 1


@pytest.mark.asyncio
class TestEvolutionWithSkillRegistry:
    """Test skill evolution integration with skill registry."""

    async def test_tracker_records_executions(self, evolution_config):
        """Test tracker records skill executions."""
        tracker = SkillEvolutionTracker(config=evolution_config)

        context = SkillContext(
            user_input="Test",
            conversation_history=[],
            current_mood="neutral",
        )

        result = SkillResult(success=True, response="Success")

        # Record execution directly
        tracker.record_execution(
            skill_name="test_skill",
            context=context,
            result=result,
        )

        metrics = tracker.get_metrics("test_skill")
        assert metrics is not None
        assert metrics.total_executions == 1

    async def test_evolution_proposal_can_reference_skill(self, temp_evolution_dir, mock_skill_class):
        """Test that evolution proposals can reference registered skills."""
        registry = SkillRegistry()
        registry.register_class(mock_skill_class)

        config = EvolutionConfig(storage_path=str(temp_evolution_dir))
        manager = EvolutionManager(config)

        # Create proposal referencing the skill
        proposal = EvolutionProposal(
            id="skill_ref_test",
            skill_name="mock_skill",
            mode=EvolutionMode.DERIVED,
            original_code="class MockSkill: pass",
            proposed_code="class MockSkillV2: pass",
            reasoning="Optimization",
            created_at=datetime.now(UTC),
        )

        await manager.store_proposal(proposal)

        # Verify stored
        retrieved = await manager.get_proposal("skill_ref_test")
        assert retrieved.skill_name == "mock_skill"


@pytest.mark.asyncio
class TestEvolutionEndToEnd:
    """End-to-end tests for the evolution workflow."""

    async def test_full_evolution_workflow(
        self, temp_evolution_dir, mock_skill_class, evolution_config
    ):
        """Test the complete evolution workflow from tracking to approval."""
        # Step 1: Track executions
        tracker = SkillEvolutionTracker(config=evolution_config)

        context = SkillContext(
            user_input="Test",
            conversation_history=[],
            current_mood="neutral",
        )

        # Record several failures
        for _ in range(5):
            result = SkillResult(
                success=False,
                response="",
                data={"error": "API timeout"},
            )
            tracker.record_execution("e2e_skill", context, result, execution_time_ms=500)

        # Step 2: Check if evolution needed
        assert tracker.needs_evolution("e2e_skill") is True

        mode = tracker.get_recommended_mode("e2e_skill")
        assert mode == "fix"

        # Step 3: Create proposal (mock generator)
        proposal = EvolutionProposal(
            id="e2e_proposal",
            skill_name="e2e_skill",
            mode=EvolutionMode.FIX,
            original_code="def execute():\n    pass",
            proposed_code="def execute():\n    try:\n        return True\n    except Exception:\n        return False",
            reasoning="Added retry logic for API timeouts",
            created_at=datetime.now(UTC),
            metrics_at_creation=tracker.get_metrics("e2e_skill").to_dict(),
        )

        # Step 4: Store in manager
        manager = EvolutionManager(evolution_config)
        await manager.store_proposal(proposal)

        # Step 5: Review and approve
        await manager.approve_proposal("e2e_proposal", reviewer="human_admin")

        # Step 6: Verify
        retrieved = await manager.get_proposal("e2e_proposal")
        assert retrieved.status == ProposalStatus.APPROVED
        assert retrieved.reviewed_by == "human_admin"

    async def test_statistics_across_full_workflow(self, temp_evolution_dir, evolution_config):
        """Test statistics tracking across the full workflow."""
        tracker = SkillEvolutionTracker(config=evolution_config)
        manager = EvolutionManager(evolution_config)

        context = SkillContext(
            user_input="Test",
            conversation_history=[],
            current_mood="neutral",
        )

        # Simulate multiple skills with different performance
        skills_data = {
            "skill_a": {"success": True, "count": 10},
            "skill_b": {"success": False, "count": 5},
            "skill_c": {"success": True, "count": 20},
        }

        for skill_name, data in skills_data.items():
            for _ in range(data["count"]):
                result = SkillResult(
                    success=data["success"],
                    response="OK" if data["success"] else "",
                    data={} if data["success"] else {"error": "fail"},
                )
                tracker.record_execution(skill_name, context, result)

        # Check tracker stats
        tracker_stats = tracker.get_statistics()
        assert tracker_stats["total_skills_tracked"] == 3
        assert tracker_stats["skills_needing_evolution"] == 1  # Only skill_b

        # Create proposals for skills needing evolution
        for skill_name in tracker.get_skills_needing_evolution():
            proposal = EvolutionProposal(
                id=f"prop_{skill_name}",
                skill_name=skill_name,
                mode=EvolutionMode.FIX,
                original_code="def execute():\n    pass",
                proposed_code="def execute():\n    return True",
                reasoning="Fix needed",
                created_at=datetime.now(UTC),
            )
            await manager.store_proposal(proposal)

        # Check manager stats
        manager_stats = manager.get_statistics()
        assert manager_stats["total_proposals"] == 1
        assert manager_stats["pending"] == 1
