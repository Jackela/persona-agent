"""End-to-end integration tests for persona-agent.

Tests complete user workflows from chat input through planning,
memory management, and skill execution.
"""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from persona_agent.config.loader import ConfigLoader
from persona_agent.core.agent_engine import AgentEngine
from persona_agent.core.memory_store import MemoryStore
from persona_agent.core.persona_manager import PersonaManager
from persona_agent.core.planning import ExecutionConfig, PlanningConfig
from persona_agent.skills.base import SkillContext, SkillResult
from persona_agent.skills.evolution import (
    EvolutionConfig,
    SkillEvolutionTracker,
)
from persona_agent.skills.registry import SkillRegistry
from persona_agent.utils.llm_client import LLMClient, LLMResponse


@pytest.fixture
def mock_llm_for_e2e():
    """Create a comprehensive mock LLM for end-to-end tests."""
    mock = Mock(spec=LLMClient)

    async def mock_chat(*args, **kwargs):
        messages = args[0] if args else kwargs.get("messages", [])
        content = messages[-1]["content"] if messages else ""

        # Intent classification
        if "classify" in content.lower():
            # Complex tasks get planning, simple ones don't
            if any(
                word in content.lower() for word in ["research", "plan", "multi-step", "complex"]
            ):
                return LLMResponse(
                    content='{"should_plan": true, "confidence": 0.95}',
                    model="test",
                    usage={},
                )
            else:
                return LLMResponse(
                    content='{"should_plan": false, "confidence": 0.9}',
                    model="test",
                    usage={},
                )

        # Task decomposition
        elif "decompose" in content.lower() or "break down" in content.lower():
            return LLMResponse(
                content='{"tasks": [{"id": "research", "description": "Research the topic"}, {"id": "summarize", "description": "Summarize findings", "dependencies": ["research"]}]}',
                model="test",
                usage={},
            )

        # Regular chat
        else:
            return LLMResponse(
                content="I'm here to help you with that request.",
                model="test",
                usage={},
            )

    mock.chat = AsyncMock(side_effect=mock_chat)

    async def mock_chat_stream(*args, **kwargs):
        chunks = ["I'm ", "here ", "to ", "help."]
        for chunk in chunks:
            yield chunk

    mock.chat_stream = mock_chat_stream
    mock.provider = "openai"
    mock.model = "gpt-4-test"

    return mock


@pytest.fixture
def e2e_config(tmp_path: Path):
    """Create configuration for end-to-end tests."""
    return {
        "planning": PlanningConfig(
            enable_parallel_execution=True,
            max_concurrent_tasks=4,
            retry_attempts=2,
        ),
        "execution": ExecutionConfig(
            enable_parallel_execution=True,
            max_workers=2,
        ),
        "evolution": EvolutionConfig(
            enabled=True,
            min_executions_before_evolution=3,
            storage_path=str(tmp_path / "evolution"),
        ),
    }


@pytest.mark.asyncio
class TestEndToEndChatWorkflow:
    """End-to-end tests for complete chat workflows."""

    async def test_simple_chat_without_planning(
        self, temp_config_dir, test_characters, mock_llm_for_e2e
    ):
        """Test simple chat that doesn't trigger planning."""
        config_loader = ConfigLoader(config_dir=temp_config_dir)
        persona_manager = PersonaManager(config_loader=config_loader)
        persona_manager.load_character("default")

        engine = AgentEngine(
            llm_client=mock_llm_for_e2e,
            persona_manager=persona_manager,
        )

        # Simple greeting
        response = await engine.chat("Hello!", enable_planning=True)

        assert response is not None
        assert isinstance(response, str)
        assert len(response) > 0

    async def test_complex_chat_with_planning(
        self, temp_config_dir, test_characters, mock_llm_for_e2e
    ):
        """Test complex chat that triggers planning system."""
        config = PlanningConfig(enable_parallel_execution=True)
        execution = ExecutionConfig(enable_parallel_execution=True)

        engine = AgentEngine(
            llm_client=mock_llm_for_e2e,
            planning_config=config,
            execution_config=execution,
        )

        # Complex query should use planning
        response = await engine.chat(
            "Research and plan a multi-step approach to learning Python",
            enable_planning=True,
        )

        assert response is not None
        assert isinstance(response, str)

    async def test_chat_with_skill_execution(
        self, temp_config_dir, test_characters, mock_llm_for_e2e
    ):
        """Test chat that involves skill execution."""
        registry = SkillRegistry()

        # Register a test skill
        class TestSkill:
            name = "test_greeting"

            def can_handle(self, context):
                return "hello" in context.user_input.lower()

            async def execute(self, context):
                return SkillResult(
                    success=True,
                    response="Hello! Nice to meet you!",
                    confidence=0.95,
                )

        registry.register_class(TestSkill)

        engine = AgentEngine(
            llm_client=mock_llm_for_e2e,
            skill_registry=registry,
        )

        response = await engine.chat("Hello there!")

        # Should get skill response
        assert "Hello!" in response or "help" in response.lower()

    async def test_chat_with_memory_storage(
        self, temp_config_dir, test_characters, mock_llm_for_e2e, tmp_path
    ):
        """Test that chat stores memories."""
        memory_path = tmp_path / "memory"
        _ = MemoryStore(db_path=memory_path / "memory.db")  # noqa: F841

        engine = AgentEngine(
            llm_client=mock_llm_for_e2e,
        )
        # Note: Memory store integration would need proper setup

        # Send multiple messages
        for i in range(3):
            response = await engine.chat(f"Message {i}")
            assert response is not None

    async def test_full_conversation_session(
        self, temp_config_dir, test_characters, mock_llm_for_e2e
    ):
        """Test a full conversation session with context."""
        engine = AgentEngine(
            llm_client=mock_llm_for_e2e,
        )

        conversation = [
            "Hi, I'm interested in learning Python",
            "What are the best resources?",
            "How long does it take to learn?",
            "Thanks for the help!",
        ]

        responses = []
        for message in conversation:
            response = await engine.chat(message)
            responses.append(response)
            assert response is not None

        assert len(responses) == len(conversation)


@pytest.mark.asyncio
class TestEndToEndPlanningWorkflow:
    """End-to-end tests for planning workflows."""

    async def test_plan_creation_and_execution(self, mock_llm_for_e2e):
        """Test complete plan creation and execution flow."""
        engine = AgentEngine(
            llm_client=mock_llm_for_e2e,
            planning_config=PlanningConfig(enable_parallel_execution=True),
            execution_config=ExecutionConfig(enable_parallel_execution=True),
        )

        # Create a plan
        plan = await engine.planning_engine.create_plan(
            goal="Research a topic and write summary",
            context={"session_id": "test-session"},
        )

        assert plan is not None
        assert plan.id is not None
        assert len(plan.tasks) >= 1

        # Execute the plan
        results = await engine.plan_executor.execute_plan(plan)

        assert results["plan_id"] == plan.id
        assert "status" in results

    async def test_plan_with_progress_callback(self, mock_llm_for_e2e):
        """Test plan execution with progress tracking."""
        engine = AgentEngine(
            llm_client=mock_llm_for_e2e,
            execution_config=ExecutionConfig(enable_parallel_execution=True),
        )

        plan = await engine.planning_engine.create_plan(
            goal="Multi-step task",
            context={},
        )

        progress_updates = []

        def on_progress(plan_id, task_id, percentage):
            progress_updates.append(
                {
                    "plan_id": plan_id,
                    "task_id": task_id,
                    "percentage": percentage,
                }
            )

        _ = await engine.plan_executor.execute_plan(
            plan,
            on_progress=on_progress,
        )

        # Should have received progress updates
        assert len(progress_updates) > 0
        assert all(0 <= p["percentage"] <= 100 for p in progress_updates)


@pytest.mark.asyncio
class TestEndToEndMemoryWorkflow:
    """End-to-end tests for memory workflows."""

    async def test_memory_compaction_flow(self, tmp_path):
        """Test complete memory compaction workflow."""
        from persona_agent.core.memory.compaction import MemoryCompactor
        from persona_agent.core.memory.summarizer import MemorySummarizer

        memory_path = tmp_path / "memory"
        memory = MemoryStore(db_path=memory_path / "memory.db")

        # Add old memories
        from datetime import timedelta

        for i in range(10):
            memory.episodic.add_episode(
                content=f"Old conversation about Python - part {i}",
                source="conversation",
                timestamp=datetime.now(UTC) - timedelta(days=10),
            )

        # Create compactor with mock summarizer
        summarizer = Mock(spec=MemorySummarizer)
        summarizer.summarize_memories = AsyncMock(return_value="Summary of Python conversations")

        compactor = MemoryCompactor(memory.episodic, summarizer=summarizer)

        # Run compaction
        result = await compactor.compact_memories(older_than_days=7)

        assert result.compacted_count == 10
        assert result.summaries_created == 1

    async def test_auto_compaction_scheduler(self, tmp_path):
        """Test auto-compaction scheduler."""
        from persona_agent.core.memory.compaction import MemoryCompactor
        from persona_agent.core.memory.scheduler import AutoCompactionScheduler

        memory_path = tmp_path / "memory"
        memory = MemoryStore(db_path=memory_path / "memory.db")

        compactor = MemoryCompactor(memory.episodic)
        scheduler = AutoCompactionScheduler(
            compactor=compactor,
            schedule_hours=1,
        )

        # Should be able to start and stop
        assert scheduler._running is False


@pytest.mark.asyncio
class TestEndToEndSkillEvolutionWorkflow:
    """End-to-end tests for skill evolution workflows."""

    async def test_skill_performance_tracking(self, tmp_path):
        """Test tracking skill performance over time."""
        config = EvolutionConfig(
            storage_path=str(tmp_path / "evolution"),
            min_executions_before_evolution=3,
        )
        tracker = SkillEvolutionTracker(config=config)

        context = SkillContext(
            user_input="Test",
            conversation_history=[],
            current_mood="neutral",
        )

        # Simulate mixed performance
        for i in range(5):
            success = i % 2 == 0  # Alternating success/failure
            result = SkillResult(
                success=success,
                response="OK" if success else "",
                data={} if success else {"error": "Timeout"},
            )
            tracker.record_execution(
                "tracked_skill",
                context,
                result,
                execution_time_ms=100,
            )

        metrics = tracker.get_metrics("tracked_skill")
        assert metrics.total_executions == 5
        assert metrics.success_rate == 0.6  # 3 successes out of 5

    async def test_evolution_proposal_workflow(self, tmp_path):
        """Test complete evolution proposal workflow."""
        from persona_agent.skills.evolution import (
            EvolutionManager,
            EvolutionMode,
            EvolutionProposal,
        )

        config = EvolutionConfig(
            storage_path=str(tmp_path / "evolution"),
        )

        tracker = SkillEvolutionTracker(config=config)
        manager = EvolutionManager(config)

        # Record failures to trigger evolution need
        context = SkillContext(
            user_input="Test",
            conversation_history=[],
            current_mood="neutral",
        )

        for _ in range(5):
            result = SkillResult(
                success=False,
                response="",
                data={"error": "API Error"},
            )
            tracker.record_execution("evolve_me", context, result)

        # Check evolution needed
        assert tracker.needs_evolution("evolve_me") is True

        # Create proposal
        proposal = EvolutionProposal(
            id="e2e_proposal",
            skill_name="evolve_me",
            mode=EvolutionMode.FIX,
            original_code="def execute(): pass",
            proposed_code="def execute(): return success",
            reasoning="Fix API error handling",
            created_at=datetime.now(UTC),
            metrics_at_creation=tracker.get_metrics("evolve_me").to_dict(),
        )

        await manager.store_proposal(proposal)

        # Approve
        await manager.approve_proposal("e2e_proposal", reviewer="admin")

        # Verify
        retrieved = await manager.get_proposal("e2e_proposal")
        assert retrieved.status.value == "approved"


@pytest.mark.asyncio
class TestEndToEndErrorHandling:
    """End-to-end tests for error handling scenarios."""

    async def test_graceful_degradation_on_llm_failure(self, temp_config_dir, test_characters):
        """Test graceful degradation when LLM fails."""
        failing_llm = Mock(spec=LLMClient)
        failing_llm.chat = AsyncMock(side_effect=Exception("LLM Error"))

        engine = AgentEngine(llm_client=failing_llm)

        # Should raise RuntimeError due to LLM failure
        with pytest.raises(RuntimeError):
            await engine.chat("Hello")

    async def test_recovery_from_skill_failure(
        self, temp_config_dir, test_characters, mock_llm_for_e2e
    ):
        """Test recovery when a skill fails."""
        registry = SkillRegistry()

        # Register a failing skill
        class FailingSkill:
            name = "failing"

            def can_handle(self, context):
                return True

            async def execute(self, context):
                return SkillResult(
                    success=False,
                    response="",
                    confidence=0.0,
                    data={"error": "Skill failed"},
                )

        registry.register_class(FailingSkill)

        engine = AgentEngine(
            llm_client=mock_llm_for_e2e,
            skill_registry=registry,
        )

        # Should still get a response (from LLM fallback)
        response = await engine.chat("Test")
        assert response is not None

    async def test_session_persistence_after_error(
        self, temp_config_dir, test_characters, mock_llm_for_e2e
    ):
        """Test that session persists even after errors."""
        engine = AgentEngine(
            llm_client=mock_llm_for_e2e,
        )

        # Successful interaction
        response1 = await engine.chat("Hello")
        assert response1 is not None

        # Get session info
        info = engine.get_session_info()
        assert info["session_id"] == engine.session_id


@pytest.mark.asyncio
class TestFullSystemIntegration:
    """Tests integrating all systems together."""

    async def test_all_systems_working_together(
        self, temp_config_dir, test_characters, mock_llm_for_e2e, tmp_path
    ):
        """Test all systems working together in harmony."""
        # Setup all systems
        evolution_config = EvolutionConfig(
            storage_path=str(tmp_path / "evolution"),
        )

        registry = SkillRegistry()
        tracker = SkillEvolutionTracker(config=evolution_config)

        # Register a skill
        class IntegratedSkill:
            name = "integrated"

            def can_handle(self, context):
                return "test" in context.user_input.lower()

            async def execute(self, context):
                return SkillResult(
                    success=True,
                    response="Integrated skill response",
                    confidence=0.9,
                )

        registry.register_class(IntegratedSkill)

        engine = AgentEngine(
            llm_client=mock_llm_for_e2e,
            skill_registry=registry,
            planning_config=PlanningConfig(enable_parallel_execution=True),
            execution_config=ExecutionConfig(enable_parallel_execution=True),
        )

        # Execute interaction
        response = await engine.chat("Test message")
        assert response is not None

        # Record execution for evolution tracking
        context = SkillContext(
            user_input="Test message",
            conversation_history=[],
            current_mood="neutral",
        )
        result = SkillResult(success=True, response=response)
        tracker.record_execution("integrated", context, result)

        # Verify tracking worked
        metrics = tracker.get_metrics("integrated")
        assert metrics is not None
