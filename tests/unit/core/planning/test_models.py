"""Unit tests for planning system models."""

from __future__ import annotations

import pytest

from persona_agent.core.planning.exceptions import CyclicDependencyError
from persona_agent.core.planning.models import (
    ExecutionConfig,
    InvalidPlanStateError,
    InvalidTaskStateError,
    Plan,
    PlanningConfig,
    PlanStatus,
    Task,
    TaskResult,
    TaskStatus,
)


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_terminal_states(self):
        """Test identification of terminal states."""
        assert TaskStatus.COMPLETED.is_terminal
        assert TaskStatus.FAILED.is_terminal
        assert TaskStatus.CANCELLED.is_terminal
        assert not TaskStatus.PENDING.is_terminal
        assert not TaskStatus.IN_PROGRESS.is_terminal
        assert not TaskStatus.BLOCKED.is_terminal

    def test_can_execute(self):
        """Test identification of executable states."""
        assert TaskStatus.PENDING.can_execute
        assert TaskStatus.BLOCKED.can_execute
        assert not TaskStatus.COMPLETED.can_execute
        assert not TaskStatus.FAILED.can_execute
        assert not TaskStatus.IN_PROGRESS.can_execute

    def test_str_representation(self):
        """Test string representation."""
        assert str(TaskStatus.PENDING) == "pending"
        assert str(TaskStatus.COMPLETED) == "completed"


class TestTaskResult:
    """Tests for TaskResult dataclass."""

    def test_success_result_factory(self):
        """Test creating success result."""
        result = TaskResult.success_result(
            output="Success output",
            data={"key": "value"},
            custom_meta="data",
        )

        assert result.success
        assert result.output == "Success output"
        assert result.data == {"key": "value"}
        assert result.metadata["custom_meta"] == "data"

    def test_failure_result_factory(self):
        """Test creating failure result."""
        result = TaskResult.failure_result(
            error="Something went wrong",
            output="Partial output",
        )

        assert not result.success
        assert result.output == "Partial output"
        assert result.metadata["error"] == "Something went wrong"


class TestTask:
    """Tests for Task dataclass."""

    def test_task_creation(self):
        """Test basic task creation."""
        task = Task(
            id="task_1",
            description="Test task description",
            dependencies=["dep1", "dep2"],
        )

        assert task.id == "task_1"
        assert task.description == "Test task description"
        assert task.dependencies == ["dep1", "dep2"]
        assert task.status == TaskStatus.PENDING
        assert task.is_ready is False

    def test_task_no_deps_is_ready(self):
        """Test task with no dependencies is ready."""
        task = Task(id="task_1", description="Test task")

        assert task.is_ready
        assert task.can_retry is False  # Not failed yet

    def test_task_validation_empty_id(self):
        """Test validation of empty task ID."""
        with pytest.raises(ValueError, match="id cannot be empty"):
            Task(id="", description="Test")

    def test_task_validation_empty_description(self):
        """Test validation of empty description."""
        with pytest.raises(ValueError, match="description cannot be empty"):
            Task(id="task_1", description="")

    def test_task_validation_negative_retries(self):
        """Test validation of negative max_retries."""
        with pytest.raises(ValueError, match="max_retries cannot be negative"):
            Task(id="task_1", description="Test", max_retries=-1)

    def test_task_validation_self_dependency(self):
        """Test validation prevents self-dependency."""
        with pytest.raises(ValueError, match="cannot depend on itself"):
            Task(id="task_1", description="Test", dependencies=["task_1"])

    def test_task_lifecycle(self):
        """Test full task lifecycle."""
        task = Task(id="task_1", description="Test task")

        # Start
        task.mark_started()
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.started_at is not None

        # Complete
        result = TaskResult.success_result(output="Done")
        task.mark_completed(result)
        assert task.status == TaskStatus.COMPLETED
        assert task.result == result
        assert task.completed_at is not None

    def test_task_mark_started_not_ready(self):
        """Test cannot start task that's not ready."""
        task = Task(id="task_1", description="Test", dependencies=["dep1"])

        with pytest.raises(InvalidTaskStateError):
            task.mark_started()

    def test_task_mark_completed_not_in_progress(self):
        """Test cannot complete task not in progress."""
        task = Task(id="task_1", description="Test")

        with pytest.raises(InvalidTaskStateError):
            task.mark_completed(TaskResult.success_result())

    def test_task_retry(self):
        """Test task retry mechanism."""
        task = Task(id="task_1", description="Test", max_retries=2)

        # Start and fail
        task.mark_started()
        task.mark_failed("Error 1", can_retry=True)

        # Should be pending again for retry
        assert task.status == TaskStatus.PENDING
        assert task.retry_count == 1

        # Fail again
        task.mark_started()
        task.mark_failed("Error 2", can_retry=True)
        assert task.retry_count == 2

        # Third failure should stick
        task.mark_started()
        task.mark_failed("Error 3", can_retry=True)
        assert task.status == TaskStatus.FAILED
        assert task.error_message == "Error 3"

    def test_task_duration(self):
        """Test duration calculation."""
        task = Task(id="task_1", description="Test")

        # No duration before completion
        assert task.duration_ms is None

        # Simulate execution
        task.mark_started()
        import time

        time.sleep(0.01)  # Small delay
        task.mark_completed(TaskResult.success_result())

        assert task.duration_ms is not None
        assert task.duration_ms >= 10  # At least 10ms

    def test_task_resolve_dependency(self):
        """Test resolving a dependency."""
        task = Task(id="task_1", description="Test", dependencies=["dep1", "dep2"])
        task.mark_blocked()

        assert not task.is_ready

        # Resolve first dependency
        assert task.resolve_dependency("dep1")
        assert not task.is_ready  # Still has dep2

        # Resolve second dependency
        assert task.resolve_dependency("dep2")
        assert task.is_ready  # Now ready
        assert task.status == TaskStatus.PENDING

    def test_task_resolve_nonexistent_dependency(self):
        """Test resolving dependency that doesn't exist."""
        task = Task(id="task_1", description="Test")

        assert not task.resolve_dependency("nonexistent")

    def test_task_to_dict_roundtrip(self):
        """Test dict serialization roundtrip."""
        task = Task(
            id="task_1",
            description="Test task",
            dependencies=["dep1"],
            max_retries=2,
            metadata={"key": "value"},
        )

        data = task.to_dict()
        restored = Task.from_dict(data)

        assert restored.id == task.id
        assert restored.description == task.description
        assert restored.dependencies == task.dependencies
        assert restored.max_retries == task.max_retries
        assert restored.metadata == task.metadata
        assert restored.status == task.status


class TestPlan:
    """Tests for Plan dataclass."""

    def test_plan_creation(self):
        """Test basic plan creation."""
        plan = Plan(id="plan_1", goal="Test goal")

        assert plan.id == "plan_1"
        assert plan.goal == "Test goal"
        assert plan.status == PlanStatus.CREATED
        assert len(plan.tasks) == 0

    def test_plan_validation_empty_id(self):
        """Test validation of empty plan ID."""
        with pytest.raises(ValueError, match="id cannot be empty"):
            Plan(id="", goal="Test")

    def test_plan_validation_empty_goal(self):
        """Test validation of empty goal."""
        with pytest.raises(ValueError, match="goal cannot be empty"):
            Plan(id="plan_1", goal="")

    def test_add_task(self):
        """Test adding tasks to plan."""
        plan = Plan(id="plan_1", goal="Test goal")
        task = Task(id="task_1", description="Test task")

        plan.add_task(task)

        assert len(plan.tasks) == 1
        assert plan.get_task("task_1") == task

    def test_add_duplicate_task(self):
        """Test cannot add duplicate task IDs."""
        plan = Plan(id="plan_1", goal="Test goal")
        task1 = Task(id="task_1", description="First")
        task2 = Task(id="task_1", description="Second")

        plan.add_task(task1)

        with pytest.raises(ValueError, match="already exists"):
            plan.add_task(task2)

    def test_get_ready_tasks(self):
        """Test getting ready tasks."""
        plan = Plan(id="plan_1", goal="Test goal")

        # Ready task (no deps)
        ready_task = Task(id="task_1", description="Ready")
        # Blocked task (has deps)
        blocked_task = Task(id="task_2", description="Blocked", dependencies=["task_1"])

        plan.add_task(ready_task)
        plan.add_task(blocked_task)

        ready = plan.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "task_1"

    def test_get_task_order_linear(self):
        """Test topological sort with linear dependencies."""
        plan = Plan(id="plan_1", goal="Test goal")

        plan.add_task(Task(id="task_3", description="Third", dependencies=["task_2"]))
        plan.add_task(Task(id="task_1", description="First"))
        plan.add_task(Task(id="task_2", description="Second", dependencies=["task_1"]))

        order = plan.get_task_order()
        assert order == ["task_1", "task_2", "task_3"]

    def test_get_task_order_dag(self):
        """Test topological sort with DAG structure."""
        plan = Plan(id="plan_1", goal="Test goal")

        #     task_1
        #    /      \
        # task_2  task_3
        #    \      /
        #     task_4

        plan.add_task(Task(id="task_1", description="Root"))
        plan.add_task(Task(id="task_2", description="Left", dependencies=["task_1"]))
        plan.add_task(Task(id="task_3", description="Right", dependencies=["task_1"]))
        plan.add_task(Task(id="task_4", description="Merge", dependencies=["task_2", "task_3"]))

        order = plan.get_task_order()
        assert order.index("task_1") < order.index("task_2")
        assert order.index("task_1") < order.index("task_3")
        assert order.index("task_2") < order.index("task_4")
        assert order.index("task_3") < order.index("task_4")

    def test_get_task_order_cycle_detection(self):
        """Test cycle detection in dependencies."""
        plan = Plan(id="plan_1", goal="Test goal")

        # Circular: task_1 -> task_2 -> task_3 -> task_1
        plan.add_task(Task(id="task_1", description="A", dependencies=["task_3"]))
        plan.add_task(Task(id="task_2", description="B", dependencies=["task_1"]))
        plan.add_task(Task(id="task_3", description="C", dependencies=["task_2"]))

        with pytest.raises(CyclicDependencyError) as exc_info:
            plan.get_task_order()

        assert "task_1" in exc_info.value.cycle_path
        assert "task_2" in exc_info.value.cycle_path
        assert "task_3" in exc_info.value.cycle_path

    def test_resolve_dependency(self):
        """Test resolving dependencies across tasks."""
        plan = Plan(id="plan_1", goal="Test goal")

        plan.add_task(Task(id="task_1", description="First"))
        plan.add_task(Task(id="task_2", description="Second", dependencies=["task_1"]))
        plan.add_task(Task(id="task_3", description="Third", dependencies=["task_1"]))

        # Initially not ready
        assert not plan.get_task("task_2").is_ready
        assert not plan.get_task("task_3").is_ready

        # Resolve dependency
        newly_ready = plan.resolve_dependency("task_1")

        assert len(newly_ready) == 2
        assert plan.get_task("task_2").is_ready
        assert plan.get_task("task_3").is_ready

    def test_plan_progress(self):
        """Test progress calculation."""
        plan = Plan(id="plan_1", goal="Test goal")

        plan.add_task(Task(id="task_1", description="First"))
        plan.add_task(Task(id="task_2", description="Second"))
        plan.add_task(Task(id="task_3", description="Third"))

        # Initial progress
        completed, total, pct = plan.progress
        assert completed == 0
        assert total == 3
        assert pct == 0

        # Complete one task
        plan.get_task("task_1").mark_started()
        plan.get_task("task_1").mark_completed(TaskResult.success_result())

        completed, total, pct = plan.progress
        assert completed == 1
        assert pct == 33

    def test_plan_is_complete(self):
        """Test plan completion detection."""
        plan = Plan(id="plan_1", goal="Test goal")
        plan.add_task(Task(id="task_1", description="First"))
        plan.add_task(Task(id="task_2", description="Second"))

        assert not plan.is_complete

        plan.get_task("task_1").mark_started()
        plan.get_task("task_1").mark_completed(TaskResult.success_result())

        assert not plan.is_complete  # task_2 still pending

        plan.get_task("task_2").mark_started()
        plan.get_task("task_2").mark_completed(TaskResult.success_result())

        assert plan.is_complete
        assert plan.all_succeeded

    def test_plan_all_succeeded_with_failures(self):
        """Test all_succeeded with failed tasks."""
        plan = Plan(id="plan_1", goal="Test goal")
        plan.add_task(Task(id="task_1", description="First"))
        plan.add_task(Task(id="task_2", description="Second"))

        plan.get_task("task_1").mark_started()
        plan.get_task("task_1").mark_completed(TaskResult.success_result())

        plan.get_task("task_2").mark_started()
        plan.get_task("task_2").mark_failed("Error")

        assert plan.is_complete
        assert not plan.all_succeeded

    def test_plan_state_transitions(self):
        """Test plan state transitions."""
        plan = Plan(id="plan_1", goal="Test goal")

        # Created -> Running
        plan.mark_running()
        assert plan.status == PlanStatus.RUNNING

        # Running -> Paused
        plan.mark_paused()
        assert plan.status == PlanStatus.PAUSED

        # Paused -> Running
        plan.mark_running()
        assert plan.status == PlanStatus.RUNNING

        # Running -> Completed
        plan.mark_completed()
        assert plan.status == PlanStatus.COMPLETED

    def test_plan_invalid_state_transitions(self):
        """Test invalid state transitions are blocked."""
        plan = Plan(id="plan_1", goal="Test goal")

        # Cannot pause from CREATED
        with pytest.raises(InvalidPlanStateError):
            plan.mark_paused()

        plan.mark_running()
        plan.mark_completed()

        # Cannot run from COMPLETED
        with pytest.raises(InvalidPlanStateError):
            plan.mark_running()

    def test_plan_mark_cancelled(self):
        """Test plan cancellation."""
        plan = Plan(id="plan_1", goal="Test goal")
        plan.add_task(Task(id="task_1", description="First"))
        plan.add_task(Task(id="task_2", description="Second"))

        # Start one task
        plan.get_task("task_1").mark_started()

        # Cancel plan
        plan.mark_cancelled()

        assert plan.status == PlanStatus.CANCELLED
        assert plan.get_task("task_1").status == TaskStatus.CANCELLED
        assert plan.get_task("task_2").status == TaskStatus.CANCELLED

    def test_execution_summary(self):
        """Test execution summary generation."""
        plan = Plan(id="plan_1", goal="Test goal", context={"key": "value"})
        plan.add_task(Task(id="task_1", description="First"))
        plan.add_task(Task(id="task_2", description="Second"))

        plan.get_task("task_1").mark_started()
        plan.get_task("task_1").mark_completed(TaskResult.success_result())

        summary = plan.execution_summary

        assert summary["plan_id"] == "plan_1"
        assert summary["goal"] == "Test goal"
        assert summary["status"] == "CREATED"
        assert summary["progress"]["completed"] == 1
        assert summary["progress"]["total"] == 2
        assert "task_1" in summary["completed_tasks"]
        assert "task_2" in summary["pending_tasks"]

    def test_plan_to_dict_roundtrip(self):
        """Test dict serialization roundtrip."""
        plan = Plan(
            id="plan_1",
            goal="Test goal",
            context={"key": "value"},
            metadata={"meta": "data"},
        )
        plan.add_task(Task(id="task_1", description="First"))
        plan.add_task(Task(id="task_2", description="Second", dependencies=["task_1"]))

        plan.get_task("task_1").mark_started()
        plan.get_task("task_1").mark_completed(TaskResult.success_result())

        data = plan.to_dict()
        restored = Plan.from_dict(data)

        assert restored.id == plan.id
        assert restored.goal == plan.goal
        assert restored.context == plan.context
        assert restored.metadata == plan.metadata
        assert len(restored.tasks) == len(plan.tasks)
        assert restored.tasks["task_1"].status == TaskStatus.COMPLETED


class TestPlanningConfig:
    """Tests for PlanningConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = PlanningConfig()

        assert config.enabled
        assert config.auto_detect
        assert config.max_concurrent_tasks == 3
        assert config.default_max_retries == 1
        assert config.enable_parallel_execution

    def test_validation_max_concurrent(self):
        """Test validation of max_concurrent_tasks."""
        with pytest.raises(ValueError, match="max_concurrent_tasks"):
            PlanningConfig(max_concurrent_tasks=0)

    def test_validation_negative_retries(self):
        """Test validation of negative retries."""
        with pytest.raises(ValueError, match="default_max_retries"):
            PlanningConfig(default_max_retries=-1)


class TestExecutionConfig:
    """Tests for ExecutionConfig."""

    def test_default_config(self):
        """Test default execution configuration."""
        config = ExecutionConfig()

        assert config.timeout_seconds is None
        assert not config.fail_fast
        assert not config.stop_on_first_error
        assert config.preserve_intermediate_results
