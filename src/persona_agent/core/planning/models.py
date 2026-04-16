"""Domain models for the planning system.

This module defines the core data structures for task planning,
including Task, Plan, and related configuration classes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, auto
from typing import Any, Self

from persona_agent.core.planning.exceptions import CyclicDependencyError


class TaskStatus(Enum):
    """Enumeration of possible task states.

    The lifecycle of a task:
    PENDING -> IN_PROGRESS -> COMPLETED/FAILED
                  |
                  v
               BLOCKED (waiting for dependencies)
    """

    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    BLOCKED = auto()  # Waiting for dependencies
    CANCELLED = auto()

    def __str__(self) -> str:
        return self.name.lower()

    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal state."""
        return self in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}

    @property
    def can_execute(self) -> bool:
        """Check if a task in this state can be executed."""
        return self in {TaskStatus.PENDING, TaskStatus.BLOCKED}


class PlanStatus(Enum):
    """Enumeration of possible plan states."""

    CREATED = auto()
    RUNNING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()

    def __str__(self) -> str:
        return self.name.lower()

    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal state."""
        return self in {PlanStatus.COMPLETED, PlanStatus.FAILED, PlanStatus.CANCELLED}

    @property
    def can_execute(self) -> bool:
        """Check if a plan in this state can be executed."""
        return self in {PlanStatus.CREATED, PlanStatus.PAUSED}


@dataclass
class TaskResult:
    """Result of a task execution.

    Attributes:
        success: Whether the task completed successfully
        data: Optional structured data returned by the task
        output: Text output from the task
        execution_time_ms: Time taken to execute in milliseconds
        metadata: Additional execution metadata
    """

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    output: str = ""
    execution_time_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success_result(
        cls,
        output: str = "",
        data: dict[str, Any] | None = None,
        **metadata: Any,
    ) -> Self:
        """Create a successful result."""
        return cls(
            success=True,
            output=output,
            data=data or {},
            metadata=metadata,
        )

    @classmethod
    def failure_result(
        cls,
        error: str,
        output: str = "",
        **metadata: Any,
    ) -> Self:
        """Create a failure result."""
        return cls(
            success=False,
            output=output,
            metadata={"error": error, **metadata},
        )


@dataclass
class Task:
    """A single task within a plan.

    Tasks are the atomic units of work in a plan. Each task has:
    - A unique identifier
    - A description of what needs to be done
    - Dependencies on other tasks
    - Status tracking
    - Retry configuration
    """

    id: str
    description: str
    status: TaskStatus = field(default=TaskStatus.PENDING)
    dependencies: list[str] = field(default_factory=list)
    result: TaskResult | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    max_retries: int = 1
    retry_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate task configuration."""
        if not self.id:
            raise ValueError("Task id cannot be empty")
        if not self.description:
            raise ValueError("Task description cannot be empty")
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if self.id in self.dependencies:
            raise ValueError(f"Task {self.id} cannot depend on itself")

    @property
    def is_ready(self) -> bool:
        """Check if task is ready for execution.

        A task is ready when:
        - It has no pending dependencies
        - It is in a pending or blocked state
        """
        return (
            self.status in {TaskStatus.PENDING, TaskStatus.BLOCKED} and len(self.dependencies) == 0
        )

    @property
    def is_completed(self) -> bool:
        """Check if task completed successfully."""
        return self.status == TaskStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        """Check if task failed."""
        return self.status == TaskStatus.FAILED

    @property
    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.is_failed and self.retry_count < self.max_retries

    @property
    def duration_ms(self) -> int | None:
        """Calculate task duration in milliseconds."""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return int(delta.total_seconds() * 1000)
        return None

    def mark_started(self) -> None:
        """Mark task as started."""
        if not self.is_ready:
            raise InvalidTaskStateError(f"Cannot start task {self.id} in state {self.status}")
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.now(UTC)

    def mark_completed(self, result: TaskResult) -> None:
        """Mark task as completed."""
        if self.status != TaskStatus.IN_PROGRESS:
            raise InvalidTaskStateError(f"Cannot complete task {self.id} in state {self.status}")
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.completed_at = datetime.now(UTC)

    def mark_failed(self, error: str, *, can_retry: bool = False) -> None:
        """Mark task as failed.

        Args:
            error: Error message describing the failure
            can_retry: Whether this failure allows retry
        """
        self.status = TaskStatus.FAILED
        self.error_message = error
        self.completed_at = datetime.now(UTC)

        if can_retry and self.retry_count < self.max_retries:
            self.retry_count += 1
            self.status = TaskStatus.PENDING
            self.error_message = None
            self.completed_at = None

    def mark_blocked(self) -> None:
        """Mark task as blocked waiting for dependencies."""
        if self.status == TaskStatus.PENDING:
            self.status = TaskStatus.BLOCKED

    def mark_cancelled(self) -> None:
        """Mark task as cancelled."""
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.now(UTC)

    def resolve_dependency(self, dependency_id: str) -> bool:
        """Remove a completed dependency.

        Args:
            dependency_id: The ID of the completed dependency

        Returns:
            True if the dependency was found and removed
        """
        if dependency_id in self.dependencies:
            self.dependencies.remove(dependency_id)
            # If no more dependencies and was blocked, go back to pending
            if not self.dependencies and self.status == TaskStatus.BLOCKED:
                self.status = TaskStatus.PENDING
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        """Convert task to dictionary representation."""
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.name,
            "dependencies": self.dependencies.copy(),
            "result": self.result.__dict__ if self.result else None,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "max_retries": self.max_retries,
            "retry_count": self.retry_count,
            "metadata": self.metadata.copy(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Create task from dictionary representation."""
        task = cls(
            id=data["id"],
            description=data["description"],
            status=TaskStatus[data["status"]],
            dependencies=data.get("dependencies", []),
            max_retries=data.get("max_retries", 1),
            retry_count=data.get("retry_count", 0),
            metadata=data.get("metadata", {}),
        )
        task.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("started_at"):
            task.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            task.completed_at = datetime.fromisoformat(data["completed_at"])
        task.error_message = data.get("error_message")
        return task


@dataclass
class Plan:
    """A plan consisting of multiple tasks with dependencies.

    Plans represent a goal decomposed into executable tasks. Tasks can have
    dependencies on other tasks, forming a directed acyclic graph (DAG).

    Attributes:
        id: Unique identifier for this plan
        goal: The high-level goal this plan aims to achieve
        tasks: Dictionary mapping task IDs to Task objects
        status: Current execution status of the plan
        context: Additional context available to all tasks
        created_at: When the plan was created
        completed_at: When the plan was completed (if applicable)
        current_task_id: Currently executing task (if any)
        metadata: Additional plan metadata
    """

    id: str
    goal: str
    tasks: dict[str, Task] = field(default_factory=dict)
    status: PlanStatus = field(default=PlanStatus.CREATED)
    context: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    current_task_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate plan configuration."""
        if not self.id:
            raise ValueError("Plan id cannot be empty")
        if not self.goal:
            raise ValueError("Plan goal cannot be empty")

    def add_task(self, task: Task) -> None:
        """Add a task to the plan.

        Args:
            task: The task to add

        Raises:
            ValueError: If a task with the same ID already exists
        """
        if task.id in self.tasks:
            raise ValueError(f"Task with ID '{task.id}' already exists in plan")
        self.tasks[task.id] = task

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        return self.tasks.get(task_id)

    def get_ready_tasks(self) -> list[Task]:
        """Get all tasks that are ready for execution."""
        return [t for t in self.tasks.values() if t.is_ready]

    def get_ready_tasks_batch(self, max_batch_size: int = 5) -> list[Task]:
        """Get a batch of ready tasks for execution.

        This method limits the number of tasks returned to prevent
        overwhelming the executor with too many concurrent tasks.
        """
        ready = self.get_ready_tasks()
        return ready[:max_batch_size]

    def get_pending_tasks(self) -> list[Task]:
        """Get all tasks that are still pending (including blocked)."""
        return [t for t in self.tasks.values() if not t.status.is_terminal]

    def get_completed_tasks(self) -> list[Task]:
        """Get all successfully completed tasks."""
        return [t for t in self.tasks.values() if t.is_completed]

    def get_failed_tasks(self) -> list[Task]:
        """Get all failed tasks."""
        return [t for t in self.tasks.values() if t.is_failed]

    def get_task_order(self) -> list[str]:
        """Return topologically sorted task IDs.

        This performs a topological sort on the task dependency graph,
        ensuring that tasks appear after their dependencies.

        Raises:
            CyclicDependencyError: If a cycle is detected in dependencies
        """
        visited: set[str] = set()
        temp_mark: set[str] = set()  # For cycle detection
        order: list[str] = []

        def visit(task_id: str, path: list[str]) -> None:
            if task_id in temp_mark:
                # Found a cycle
                cycle_start = path.index(task_id)
                cycle_path = path[cycle_start:] + [task_id]
                raise CyclicDependencyError(cycle_path=cycle_path)

            if task_id in visited:
                return

            temp_mark.add(task_id)
            path.append(task_id)

            task = self.tasks[task_id]
            for dep_id in task.dependencies:
                if dep_id in self.tasks:
                    visit(dep_id, path)
                # Silently ignore dependencies on non-existent tasks

            path.pop()
            temp_mark.remove(task_id)
            visited.add(task_id)
            order.append(task_id)

        for task_id in self.tasks:
            if task_id not in visited:
                visit(task_id, [])

        return order

    def resolve_dependency(self, completed_task_id: str) -> list[Task]:
        """Remove a completed dependency from all tasks.

        Args:
            completed_task_id: ID of the completed task

        Returns:
            List of tasks that became ready due to this resolution
        """
        newly_ready: list[Task] = []

        for task in self.tasks.values():
            was_not_ready = not task.is_ready
            if task.resolve_dependency(completed_task_id):
                if was_not_ready and task.is_ready:
                    newly_ready.append(task)

        return newly_ready

    def update_task_status(self, task_id: str, status: TaskStatus) -> None:
        """Update the status of a task and potentially the plan."""
        task = self.tasks.get(task_id)
        if task:
            task.status = status
            if status == TaskStatus.COMPLETED:
                self.resolve_dependency(task_id)

    def mark_running(self) -> None:
        """Mark the plan as running."""
        if not self.status.can_execute:
            raise InvalidPlanStateError(
                plan_id=self.id,
                current_state=self.status.name,
                required_state=["CREATED", "PAUSED"],
            )
        self.status = PlanStatus.RUNNING

    def mark_completed(self) -> None:
        """Mark the plan as completed."""
        self.status = PlanStatus.COMPLETED
        self.completed_at = datetime.now(UTC)
        self.current_task_id = None

    def mark_failed(self) -> None:
        """Mark the plan as failed."""
        self.status = PlanStatus.FAILED
        self.completed_at = datetime.now(UTC)
        self.current_task_id = None

    def mark_paused(self) -> None:
        """Mark the plan as paused."""
        if self.status != PlanStatus.RUNNING:
            raise InvalidPlanStateError(
                plan_id=self.id,
                current_state=self.status.name,
                required_state="RUNNING",
            )
        self.status = PlanStatus.PAUSED

    def mark_cancelled(self) -> None:
        """Mark the plan as cancelled."""
        # Cancel all non-terminal tasks
        for task in self.tasks.values():
            if not task.status.is_terminal:
                task.mark_cancelled()
        self.status = PlanStatus.CANCELLED
        self.completed_at = datetime.now(UTC)

    @property
    def is_complete(self) -> bool:
        """Check if all tasks are in terminal states."""
        return all(t.status.is_terminal for t in self.tasks.values())

    @property
    def all_succeeded(self) -> bool:
        """Check if all tasks completed successfully."""
        return all(t.is_completed for t in self.tasks.values())

    @property
    def progress(self) -> tuple[int, int, int]:
        """Return progress tuple (completed, total, percentage).

        Returns:
            Tuple of (completed_count, total_count, percentage)
        """
        total = len(self.tasks)
        completed = sum(1 for t in self.tasks.values() if t.status.is_terminal)
        percentage = int(completed / total * 100) if total > 0 else 0
        return completed, total, percentage

    @property
    def execution_summary(self) -> dict[str, Any]:
        """Generate an execution summary."""
        completed, total, percentage = self.progress
        return {
            "plan_id": self.id,
            "goal": self.goal,
            "status": self.status.name,
            "progress": {
                "completed": completed,
                "total": total,
                "percentage": percentage,
            },
            "completed_tasks": [t.id for t in self.get_completed_tasks()],
            "failed_tasks": [t.id for t in self.get_failed_tasks()],
            "pending_tasks": [t.id for t in self.get_pending_tasks()],
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert plan to dictionary representation."""
        return {
            "id": self.id,
            "goal": self.goal,
            "tasks": {tid: t.to_dict() for tid, t in self.tasks.items()},
            "status": self.status.name,
            "context": self.context.copy(),
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "current_task_id": self.current_task_id,
            "metadata": self.metadata.copy(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Create plan from dictionary representation."""
        plan = cls(
            id=data["id"],
            goal=data["goal"],
            status=PlanStatus[data["status"]],
            context=data.get("context", {}),
            metadata=data.get("metadata", {}),
        )
        plan.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("completed_at"):
            plan.completed_at = datetime.fromisoformat(data["completed_at"])
        plan.current_task_id = data.get("current_task_id")

        # Load tasks
        for task_data in data.get("tasks", {}).values():
            plan.add_task(Task.from_dict(task_data))

        return plan


class InvalidTaskStateError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class InvalidPlanStateError(Exception):
    """Raised when an invalid plan state transition is attempted."""

    def __init__(
        self,
        *,
        plan_id: str,
        current_state: str,
        required_state: str | list[str],
    ) -> None:
        states = [required_state] if isinstance(required_state, str) else required_state
        super().__init__(
            f"Plan {plan_id} is in state '{current_state}', "
            f"but required state is one of: {states}"
        )
        self.plan_id = plan_id
        self.current_state = current_state
        self.required_states = states


# Configuration classes
@dataclass
class PlanningConfig:
    """Configuration for the planning system."""

    enabled: bool = True
    auto_detect: bool = True
    max_concurrent_tasks: int = 3
    default_max_retries: int = 1
    enable_parallel_execution: bool = True
    progress_callback_interval_ms: int = 100

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.max_concurrent_tasks < 1:
            raise ValueError("max_concurrent_tasks must be at least 1")
        if self.default_max_retries < 0:
            raise ValueError("default_max_retries cannot be negative")


@dataclass
class ExecutionConfig:
    """Configuration for plan execution."""

    timeout_seconds: float | None = None
    fail_fast: bool = False
    stop_on_first_error: bool = False
    preserve_intermediate_results: bool = True
    enable_parallel_execution: bool = True
    max_concurrent_tasks: int = 3


__all__ = [
    "TaskStatus",
    "PlanStatus",
    "Task",
    "TaskResult",
    "Plan",
    "PlanningConfig",
    "ExecutionConfig",
    "InvalidTaskStateError",
    "InvalidPlanStateError",
]
