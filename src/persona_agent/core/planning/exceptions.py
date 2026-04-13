"""Exceptions for the planning system.

This module defines all custom exceptions used throughout the planning
system, following a hierarchical structure for precise error handling.
"""

from __future__ import annotations


class PlanningError(Exception):
    """Base exception for all planning-related errors."""

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class PlanCreationError(PlanningError):
    """Raised when plan creation fails.

    This can occur due to:
    - Invalid goal specification
    - LLM generation failures
    - Parsing errors
    """

    pass


class PlanExecutionError(PlanningError):
    """Raised when plan execution encounters an unrecoverable error."""

    def __init__(
        self,
        message: str,
        *,
        plan_id: str | None = None,
        failed_task_id: str | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.plan_id = plan_id
        self.failed_task_id = failed_task_id


class TaskExecutionError(PlanningError):
    """Raised when an individual task fails execution.

    This is typically caught and handled by the PlanExecutor, which may
    retry the task or mark it as failed depending on configuration.
    """

    def __init__(
        self,
        message: str,
        *,
        task_id: str,
        attempt: int = 1,
        max_retries: int = 1,
        details: dict | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.task_id = task_id
        self.attempt = attempt
        self.max_retries = max_retries
        self.can_retry = attempt < max_retries


class DependencyError(PlanningError):
    """Raised when task dependencies cannot be satisfied.

    This typically indicates a deadlock or circular dependency.
    """

    def __init__(
        self,
        message: str,
        *,
        task_id: str,
        unresolved_dependencies: list[str],
    ) -> None:
        super().__init__(message)
        self.task_id = task_id
        self.unresolved_dependencies = unresolved_dependencies


class CyclicDependencyError(DependencyError):
    """Raised when a circular dependency is detected in the task graph."""

    def __init__(self, *, cycle_path: list[str]) -> None:
        message = f"Circular dependency detected: {' -> '.join(cycle_path)}"
        super().__init__(message, task_id=cycle_path[0], unresolved_dependencies=cycle_path)
        self.cycle_path = cycle_path


class PlanNotFoundError(PlanningError):
    """Raised when attempting to access a non-existent plan."""

    def __init__(self, plan_id: str) -> None:
        super().__init__(f"Plan not found: {plan_id}")
        self.plan_id = plan_id


class InvalidPlanStateError(PlanningError):
    """Raised when an operation is attempted on a plan in an invalid state."""

    def __init__(
        self,
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


class PlanningConfigError(PlanningError):
    """Raised when planning configuration is invalid."""

    pass


__all__ = [
    "PlanningError",
    "PlanCreationError",
    "PlanExecutionError",
    "TaskExecutionError",
    "DependencyError",
    "CyclicDependencyError",
    "PlanNotFoundError",
    "InvalidPlanStateError",
    "PlanningConfigError",
]
