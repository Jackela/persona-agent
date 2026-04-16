"""Integration tests for the planning system.

Tests the planning system integration with AgentEngine, including
plan creation, execution, and error handling in real workflows.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from persona_agent.core.agent_engine import AgentEngine
from persona_agent.core.planning import (
    ExecutionConfig,
    PlanExecutor,
    PlanningConfig,
    PlanningEngine,
)
from persona_agent.core.planning.models import Plan, Task, TaskResult, TaskStatus
from persona_agent.utils.llm_client import LLMClient, LLMResponse


@pytest.fixture
def mock_llm_for_planning():
    """Create a mock LLM that returns appropriate planning responses."""
    mock = Mock(spec=LLMClient)

    async def mock_chat(*args, **kwargs):
        messages = args[0] if args else kwargs.get("messages", [])
        content = messages[-1]["content"] if messages else ""

        # Return different responses based on the prompt
        if "classify" in content.lower() or "intent" in content.lower():
            return LLMResponse(
                content='{"should_plan": true, "confidence": 0.9, "reason": "complex_task"}',
                model="test",
                usage={},
            )
        elif "decompose" in content.lower() or "task" in content.lower():
            return LLMResponse(
                content='{"tasks": [{"id": "task_1", "description": "Research topic"}, {"id": "task_2", "description": "Summarize findings", "dependencies": ["task_1"]}]}',
                model="test",
                usage={},
            )
        elif "refine" in content.lower():
            return LLMResponse(
                content='{"refined_tasks": [{"id": "task_1", "description": "Research topic thoroughly"}, {"id": "task_2", "description": "Write summary", "dependencies": ["task_1"]}]}',
                model="test",
                usage={},
            )
        else:
            return LLMResponse(
                content="Test response",
                model="test",
                usage={},
            )

    mock.chat = AsyncMock(side_effect=mock_chat)

    async def mock_chat_stream(*args, **kwargs):
        chunks = ["Test ", "response"]
        for chunk in chunks:
            yield chunk

    mock.chat_stream = mock_chat_stream
    mock.provider = "openai"
    mock.model = "gpt-4-test"

    return mock


@pytest.fixture
def planning_config():
    """Create a planning configuration for testing."""
    return PlanningConfig(
        enabled=True,
        enable_parallel_execution=True,
        max_concurrent_tasks=4,
        default_max_retries=2,
    )


@pytest.fixture
def execution_config():
    """Create an execution configuration for testing."""
    return ExecutionConfig(
        enable_parallel_execution=True,
        max_concurrent_tasks=4,
    )


@pytest.fixture
def mock_agent_engine():
    """Create a properly mocked AgentEngine."""
    engine = Mock(spec=AgentEngine)
    engine.session_id = "test-session"
    engine.persona_manager = Mock()
    engine.persona_manager.get_mood_engine.return_value = Mock()
    engine.persona_manager.get_mood_engine.return_value.current_state = Mock()
    engine.persona_manager.get_mood_engine.return_value.current_state.name = "neutral"
    return engine


@pytest.mark.asyncio
class TestPlanningModelsIntegration:
    """Test Planning system models work correctly."""

    async def test_plan_creation_and_task_management(self):
        """Test creating a plan and managing tasks."""
        plan = Plan(id="test_plan", goal="Test goal")

        # Add tasks
        task1 = Task(id="task_1", description="First task")
        task2 = Task(id="task_2", description="Second task", dependencies=["task_1"])

        plan.add_task(task1)
        plan.add_task(task2)

        assert len(plan.tasks) == 2
        assert plan.get_task("task_1") == task1
        assert plan.get_task("task_2") == task2

        # Check task order (topological sort)
        order = plan.get_task_order()
        assert order.index("task_1") < order.index("task_2")

    async def test_task_state_transitions(self):
        """Test task state machine transitions."""
        task = Task(id="test_task", description="Test")

        # Initial state
        assert task.status == TaskStatus.PENDING
        assert task.is_ready

        # Start task
        task.mark_started()
        assert task.status == TaskStatus.IN_PROGRESS

        # Complete task
        result = TaskResult(success=True, output="Test output")
        task.mark_completed(result)
        assert task.status == TaskStatus.COMPLETED
        assert task.is_completed

    async def test_sequential_dependencies(self):
        """Test sequential task dependencies."""
        plan = Plan(id="seq_plan", goal="Sequential test")

        task1 = Task(id="step1", description="First step")
        task2 = Task(id="step2", description="Second step", dependencies=["step1"])
        task3 = Task(id="step3", description="Third step", dependencies=["step2"])

        plan.add_task(task1)
        plan.add_task(task2)
        plan.add_task(task3)

        # Initially only task1 is ready
        ready = plan.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "step1"

        # Complete task1
        task1.mark_started()
        task1.mark_completed(TaskResult(success=True))
        newly_ready = plan.resolve_dependency("step1")

        # Now task2 should be ready
        assert len(newly_ready) == 1
        assert newly_ready[0].id == "step2"

    async def test_parallel_task_execution_readiness(self):
        """Test parallel task readiness detection."""
        plan = Plan(id="par_plan", goal="Parallel test")

        # Add independent tasks
        for i in range(3):
            task = Task(id=f"parallel_{i}", description=f"Task {i}")
            plan.add_task(task)

        # All should be ready initially
        ready = plan.get_ready_tasks()
        assert len(ready) == 3

        # Check batch limiting
        batch = plan.get_ready_tasks_batch(max_batch_size=2)
        assert len(batch) == 2

    async def test_plan_progress_tracking(self):
        """Test plan progress calculation."""
        plan = Plan(id="prog_plan", goal="Progress test")

        for i in range(5):
            plan.add_task(Task(id=f"task_{i}", description=f"Task {i}"))

        # No tasks completed
        completed, total, pct = plan.progress
        assert completed == 0
        assert total == 5
        assert pct == 0

        # Complete some tasks
        for i in range(3):
            task = plan.get_task(f"task_{i}")
            task.mark_started()
            task.mark_completed(TaskResult(success=True))

        completed, total, pct = plan.progress
        assert completed == 3
        assert pct == 60


@pytest.mark.asyncio
class TestPlanningEngineIntegration:
    """Test PlanningEngine integration."""

    async def test_planning_engine_classifies_intent(self, mock_llm_for_planning, planning_config):
        """Test that planning engine correctly classifies intent."""
        engine = PlanningEngine(Mock(), planning_config)
        engine.llm_client = mock_llm_for_planning

        # Test complex task that should trigger planning
        should_plan = await engine.should_plan(
            "Research the history of artificial intelligence and write a summary"
        )

        assert should_plan is True

    async def test_planning_engine_skips_simple_queries(self, planning_config):
        """Test that planning engine skips planning for simple queries."""
        engine = PlanningEngine(Mock(), planning_config)
        # No LLM needed - heuristic should handle simple queries

        # Simple query
        should_plan = await engine.should_plan("Hello")

        # Should be False due to heuristic
        assert should_plan is False


@pytest.mark.asyncio
class TestPlanExecutorIntegration:
    """Test PlanExecutor integration."""

    async def test_executor_handles_empty_plan(self, mock_agent_engine, execution_config):
        """Test executor handles empty plan."""
        executor = PlanExecutor(mock_agent_engine, execution_config)

        empty_plan = Plan(id="empty_plan", goal="Empty plan")

        results = await executor.execute_plan(empty_plan)

        assert results["status"] == "completed"
        assert results["completed_tasks"] == []

    async def test_executor_runs_simple_plan(self, mock_agent_engine, execution_config):
        """Test executor runs a simple plan."""
        executor = PlanExecutor(mock_agent_engine, execution_config)

        plan = Plan(id="simple_plan", goal="Simple test")
        plan.add_task(Task(id="task1", description="Simple task"))

        results = await executor.execute_plan(plan)

        assert results["plan_id"] == plan.id
        assert "status" in results


@pytest.mark.asyncio
class TestPlanningErrorHandling:
    """Test error handling in planning system."""

    async def test_graceful_failure_when_llm_unavailable(self, planning_config):
        """Test graceful degradation when LLM is unavailable."""
        # Create LLM that always fails
        failing_llm = Mock(spec=LLMClient)
        failing_llm.chat = AsyncMock(side_effect=Exception("LLM unavailable"))

        engine = PlanningEngine(Mock(), planning_config)
        engine.llm_client = failing_llm

        # Should not crash, should fall back to heuristic
        should_plan = await engine.should_plan("Complex task")

        # Should return False (heuristic default) rather than crash
        assert isinstance(should_plan, bool)

    async def test_circular_dependency_detection(self):
        """Test detection of circular dependencies."""
        plan = Plan(id="circular_plan", goal="Circular test")

        # Create circular dependency: A -> B -> C -> A
        task_a = Task(id="A", description="Task A", dependencies=["C"])
        task_b = Task(id="B", description="Task B", dependencies=["A"])
        task_c = Task(id="C", description="Task C", dependencies=["B"])

        plan.add_task(task_a)
        plan.add_task(task_b)
        plan.add_task(task_c)

        # Detect cycles via get_task_order which raises CyclicDependencyError
        from persona_agent.core.planning.exceptions import CyclicDependencyError

        with pytest.raises(CyclicDependencyError) as exc_info:
            plan.get_task_order()

        assert exc_info.value.cycle_path is not None
        assert len(exc_info.value.cycle_path) > 0

    async def test_task_validation_prevents_self_dependency(self):
        """Test that tasks cannot depend on themselves."""
        with pytest.raises(ValueError) as exc_info:
            Task(id="self_dep", description="Self-dep", dependencies=["self_dep"])

        assert "cannot depend on itself" in str(exc_info.value)

    async def test_plan_validation_requires_id(self):
        """Test that plans require an ID."""
        with pytest.raises(ValueError) as exc_info:
            Plan(id="", goal="Test")

        assert "id cannot be empty" in str(exc_info.value)


@pytest.mark.asyncio
class TestPlanningConfigIntegration:
    """Test configuration integration."""

    async def test_planning_config_validation(self):
        """Test planning configuration validation."""
        # Valid config
        config = PlanningConfig(max_concurrent_tasks=5, default_max_retries=3)
        assert config.max_concurrent_tasks == 5
        assert config.default_max_retries == 3

        # Invalid max_concurrent_tasks
        with pytest.raises(ValueError) as exc_info:
            PlanningConfig(max_concurrent_tasks=0)
        assert "max_concurrent_tasks" in str(exc_info.value)

        # Invalid max_retries
        with pytest.raises(ValueError) as exc_info:
            PlanningConfig(default_max_retries=-1)
        assert "max_retries" in str(exc_info.value)

    async def test_execution_config_defaults(self):
        """Test execution configuration defaults."""
        config = ExecutionConfig()

        assert config.enable_parallel_execution is True
        assert config.max_concurrent_tasks == 3
        assert config.fail_fast is False
