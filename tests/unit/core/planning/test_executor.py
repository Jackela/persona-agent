"""Unit tests for plan executor."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from persona_agent.core.planning.exceptions import (
    InvalidPlanStateError,
    PlanExecutionError,
    PlanNotFoundError,
)
from persona_agent.core.planning.executor import PlanExecutor, TaskExecutor
from persona_agent.core.planning.models import (
    ExecutionConfig,
    Plan,
    PlanStatus,
    Task,
    TaskResult,
    TaskStatus,
)


class TestTaskExecutor:
    """Tests for TaskExecutor."""

    @pytest.fixture
    def mock_agent_engine(self):
        engine = AsyncMock()
        engine.chat.return_value = "Task completed successfully"
        return engine

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_agent_engine):
        """Test successful task execution."""
        executor = TaskExecutor(mock_agent_engine)

        plan = Plan(id="plan_1", goal="Test goal")
        task = Task(id="task_1", description="Test task")

        result = await executor.execute(task, plan)

        assert result.success
        assert result.output == "Task completed successfully"
        assert result.execution_time_ms >= 0  # Can be 0ms for very fast execution

    @pytest.mark.asyncio
    async def test_execute_no_agent_engine(self):
        """Test execution without agent engine."""
        executor = TaskExecutor(None)

        plan = Plan(id="plan_1", goal="Test goal")
        task = Task(id="task_1", description="Test task")

        result = await executor.execute(task, plan)

        assert not result.success
        assert "No agent engine" in result.metadata["error"]

    @pytest.mark.asyncio
    async def test_execute_failure(self, mock_agent_engine):
        """Test task execution failure."""
        mock_agent_engine.chat.side_effect = Exception("LLM error")

        executor = TaskExecutor(mock_agent_engine)

        plan = Plan(id="plan_1", goal="Test goal")
        task = Task(id="task_1", description="Test task")

        result = await executor.execute(task, plan)

        assert not result.success
        assert "LLM error" in result.metadata["error"]

    @pytest.mark.asyncio
    async def test_build_task_context_with_dependencies(self, mock_agent_engine):
        """Test context building with completed dependencies."""
        executor = TaskExecutor(mock_agent_engine)

        plan = Plan(id="plan_1", goal="Test goal")
        plan.add_task(Task(id="dep_task", description="Dependency"))
        plan.add_task(Task(id="main_task", description="Main task", dependencies=["dep_task"]))

        # Complete the dependency
        plan.get_task("dep_task").mark_started()
        plan.get_task("dep_task").mark_completed(
            TaskResult.success_result(output="Dependency result")
        )

        context = executor._build_task_context(plan.get_task("main_task"), plan)

        assert "Test goal" in context
        assert "Main task" in context
        assert "Dependency result" in context


class TestPlanExecutor:
    """Tests for PlanExecutor."""

    @pytest.fixture
    def mock_agent_engine(self):
        engine = AsyncMock()
        engine.chat.return_value = "Completed"
        return engine

    @pytest.fixture
    def executor(self, mock_agent_engine):
        return PlanExecutor(mock_agent_engine)

    @pytest.mark.asyncio
    async def test_execute_plan_success(self, executor):
        """Test successful plan execution."""
        plan = Plan(id="plan_1", goal="Test goal")
        plan.add_task(Task(id="task_1", description="First"))
        plan.add_task(Task(id="task_2", description="Second", dependencies=["task_1"]))

        results = await executor.execute_plan(plan)

        assert results["status"] == "completed"
        assert "task_1" in results["completed_tasks"]
        assert "task_2" in results["completed_tasks"]
        assert plan.status == PlanStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_plan_with_failures(self, executor, mock_agent_engine):
        """Test plan execution with task failures."""
        mock_agent_engine.chat.side_effect = ["OK", Exception("Error")]

        plan = Plan(id="plan_1", goal="Test goal")
        plan.add_task(Task(id="task_1", description="First"))
        plan.add_task(Task(id="task_2", description="Second"))

        results = await executor.execute_plan(plan)

        assert results["status"] == "failed"
        assert len(results["completed_tasks"]) == 1
        assert len(results["failed_tasks"]) == 1
        assert plan.status == PlanStatus.FAILED

    @pytest.mark.asyncio
    async def test_execute_plan_invalid_state(self, executor):
        """Test executing plan in invalid state."""
        plan = Plan(id="plan_1", goal="Test goal")
        plan.mark_completed()

        with pytest.raises(InvalidPlanStateError):
            await executor.execute_plan(plan)

    @pytest.mark.asyncio
    async def test_execute_plan_progress_callback(self, executor):
        """Test progress callback."""
        progress_calls = []

        def on_progress(plan_id, task_id, pct):
            progress_calls.append((plan_id, task_id, pct))

        plan = Plan(id="plan_1", goal="Test goal")
        plan.add_task(Task(id="task_1", description="First"))

        await executor.execute_plan(plan, on_progress=on_progress)

        assert len(progress_calls) == 1
        assert progress_calls[0][0] == "plan_1"
        assert progress_calls[0][1] == "task_1"
        assert progress_calls[0][2] == 100

    @pytest.mark.asyncio
    async def test_execute_plan_task_callbacks(self, executor):
        """Test task completion and failure callbacks."""
        completed_tasks = []
        failed_tasks = []

        def on_complete(plan_id, task, result):
            completed_tasks.append(task.id)

        def on_fail(plan_id, task, result):
            failed_tasks.append(task.id)

        plan = Plan(id="plan_1", goal="Test goal")
        plan.add_task(Task(id="task_1", description="First"))

        await executor.execute_plan(
            plan,
            on_task_complete=on_complete,
            on_task_fail=on_fail,
        )

        assert "task_1" in completed_tasks
        assert len(failed_tasks) == 0

    @pytest.mark.asyncio
    async def test_pause_and_resume_plan(self, executor):
        """Test pausing and resuming plan execution."""
        plan = Plan(id="plan_1", goal="Test goal")
        plan.add_task(Task(id="task_1", description="First"))

        # Pre-register the plan and its lock (simulate execution in progress)
        executor._active_plans[plan.id] = plan
        executor._execution_locks[plan.id] = asyncio.Lock()

        # Mark as running (as execute_plan would do)
        plan.mark_running()

        # Pause
        result = await executor.pause_plan(plan.id)
        assert result is True
        assert plan.status == PlanStatus.PAUSED

        # Resume
        results = await executor.resume_plan(plan.id)
        assert results["status"] == "completed"

    @pytest.mark.asyncio
    async def test_pause_plan_not_found(self, executor):
        """Test pausing non-existent plan."""
        with pytest.raises(PlanNotFoundError):
            await executor.pause_plan("nonexistent")

    @pytest.mark.asyncio
    async def test_cancel_plan(self, executor):
        """Test cancelling a plan."""
        plan = Plan(id="plan_1", goal="Test goal")
        plan.add_task(Task(id="task_1", description="First"))

        # Register plan first
        executor._active_plans[plan.id] = plan
        executor._execution_locks[plan.id] = asyncio.Lock()

        result = await executor.cancel_plan(plan.id)

        assert result is True
        assert plan.status == PlanStatus.CANCELLED
        assert plan.get_task("task_1").status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_plan_not_active(self, executor):
        """Test cancelling non-active plan."""
        with pytest.raises(PlanNotFoundError):
            await executor.cancel_plan("nonexistent")

    @pytest.mark.asyncio
    async def test_cancel_plan_already_complete(self, executor):
        """Test cancelling already completed plan."""
        plan = Plan(id="plan_1", goal="Test goal")
        plan.mark_completed()

        executor._active_plans[plan.id] = plan
        executor._execution_locks[plan.id] = asyncio.Lock()

        result = await executor.cancel_plan(plan.id)

        assert result is False  # Already terminal

    @pytest.mark.asyncio
    async def test_parallel_execution(self, mock_agent_engine):
        """Test parallel task execution."""
        config = ExecutionConfig(enable_parallel_execution=True)
        executor = PlanExecutor(mock_agent_engine, config)

        plan = Plan(id="plan_1", goal="Test goal")
        # Two independent tasks
        plan.add_task(Task(id="task_1", description="First"))
        plan.add_task(Task(id="task_2", description="Second"))

        results = await executor.execute_plan(plan)

        assert results["status"] == "completed"
        assert len(results["completed_tasks"]) == 2

    @pytest.mark.asyncio
    async def test_stop_on_first_error(self, mock_agent_engine):
        """Test stopping on first error."""
        mock_agent_engine.chat.side_effect = Exception("First error")

        config = ExecutionConfig(stop_on_first_error=True)
        executor = PlanExecutor(mock_agent_engine, config)

        plan = Plan(id="plan_1", goal="Test goal")
        plan.add_task(Task(id="task_1", description="First"))
        plan.add_task(Task(id="task_2", description="Second"))

        with pytest.raises(PlanExecutionError):
            await executor.execute_plan(plan)

    @pytest.mark.asyncio
    async def test_deadlock_detection(self, executor):
        """Test detection of deadlocked tasks."""
        plan = Plan(id="plan_1", goal="Test goal")
        # Tasks with unresolved dependencies (tasks don't exist)
        plan.add_task(Task(id="task_1", description="First", dependencies=["nonexistent"]))

        results = await executor.execute_plan(plan)

        assert results["status"] == "failed"
        assert "task_1" in results["failed_tasks"]

    def test_get_plan_status(self, executor):
        """Test getting plan status."""
        plan = Plan(id="plan_1", goal="Test")
        executor._active_plans["plan_1"] = plan

        assert executor.get_plan_status("plan_1") is plan
        assert executor.get_plan_status("nonexistent") is None

    def test_list_active_plans(self, executor):
        """Test listing active plans."""
        executor._active_plans["plan_1"] = MagicMock()
        executor._active_plans["plan_2"] = MagicMock()

        active = executor.list_active_plans()

        assert set(active) == {"plan_1", "plan_2"}
