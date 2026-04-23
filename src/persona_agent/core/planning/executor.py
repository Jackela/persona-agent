"""Plan executor for managing plan execution lifecycle.

This module provides the PlanExecutor class which is responsible for:
- Executing plans with proper state management
- Handling task dependencies and parallel execution
- Managing retries and error recovery
- Providing progress callbacks
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from persona_agent.core.planning.exceptions import (
    InvalidPlanStateError,
    PlanExecutionError,
    PlanNotFoundError,
    TaskExecutionError,
)
from persona_agent.core.planning.models import (
    ExecutionConfig,
    Plan,
    PlanStatus,
    Task,
    TaskResult,
    TaskStatus,
)

if TYPE_CHECKING:
    from persona_agent.core.agent_engine import AgentEngine

logger = logging.getLogger(__name__)


ProgressCallback = Callable[[str, str, int], None]
"""Callback type: (plan_id, task_id, progress_percentage)"""

TaskCallback = Callable[[str, Task, TaskResult], None]
"""Callback type: (plan_id, task, result)"""


class TaskExecutor:
    """Executes individual tasks using the agent engine."""

    def __init__(self, agent_engine: AgentEngine | None = None) -> None:
        self.agent_engine = agent_engine

    async def execute(
        self,
        task: Task,
        plan: Plan,
    ) -> TaskResult:
        """Execute a single task.

        Args:
            task: The task to execute
            plan: The parent plan for context

        Returns:
            TaskResult with execution outcome

        Raises:
            TaskExecutionError: If execution fails
        """
        if not self.agent_engine:
            return TaskResult.failure_result(error="No agent engine available for task execution")

        # Build task context
        context = self._build_task_context(task, plan)

        start_time = time.monotonic()

        try:
            response = await self.agent_engine.chat(
                user_input=context,
                stream=False,
                enable_planning=False,
            )

            execution_time_ms = int((time.monotonic() - start_time) * 1000)

            response_str = response if isinstance(response, str) else ""

            return TaskResult.success_result(
                output=response_str,
                execution_time_ms=execution_time_ms,
            )

        except Exception as e:
            execution_time_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(f"Task {task.id} execution failed: {e}")

            raise TaskExecutionError(
                str(e),
                task_id=task.id,
                attempt=task.retry_count + 1,
                max_retries=task.max_retries,
            ) from e

    def _build_task_context(self, task: Task, plan: Plan) -> str:
        """Build context for task execution.

        This creates a prompt that gives the task all necessary context
        including the goal, previous results, and current task description.
        """
        lines = [
            f"Goal: {plan.goal}",
            "",
            f"Current task: {task.description}",
        ]

        # Add completed dependencies
        completed_results = []
        for dep_id in task.dependencies:
            if dep_id in plan.tasks:
                dep_task = plan.tasks[dep_id]
                if dep_task.is_completed and dep_task.result:
                    completed_results.append(
                        f"- {dep_task.description}: {dep_task.result.output[:200]}"
                    )

        if completed_results:
            lines.extend(["", "Previous results:"])
            lines.extend(completed_results)

        lines.extend(
            [
                "",
                "Execute this task and provide the result.",
            ]
        )

        return "\n".join(lines)


class PlanExecutor:
    """Execute plans with state management and error handling.

    The plan executor manages the lifecycle of plan execution, including:
    - Task scheduling based on dependencies
    - Parallel execution of independent tasks
    - Retry handling for failed tasks
    - Progress reporting via callbacks

    Example:
        executor = PlanExecutor(agent_engine)

        async def on_progress(plan_id, task_id, pct):
            print(f"Progress: {pct}%")

        results = await executor.execute_plan(
            plan,
            on_progress=on_progress
        )
    """

    def __init__(
        self,
        agent_engine: AgentEngine | None = None,
        config: ExecutionConfig | None = None,
    ) -> None:
        self.agent_engine = agent_engine
        self.config = config or ExecutionConfig()
        self.task_executor = TaskExecutor(agent_engine)
        self._active_plans: dict[str, Plan] = {}
        self._execution_locks: dict[str, asyncio.Lock] = {}

    async def execute_plan(
        self,
        plan: Plan,
        *,
        on_progress: ProgressCallback | None = None,
        on_task_complete: TaskCallback | None = None,
        on_task_fail: TaskCallback | None = None,
    ) -> dict[str, Any]:
        """Execute a plan to completion.

        Args:
            plan: The plan to execute
            on_progress: Optional callback for progress updates
            on_task_complete: Optional callback when a task completes
            on_task_fail: Optional callback when a task fails

        Returns:
            Execution results summary

        Raises:
            PlanExecutionError: If execution encounters an unrecoverable error
            InvalidPlanStateError: If the plan is not in a valid state to execute
        """
        # Validate plan state
        if not plan.status.can_execute:
            raise InvalidPlanStateError(
                plan_id=plan.id,
                current_state=plan.status.name,
                required_state=["CREATED", "PAUSED"],
            )

        # Register plan as active
        self._active_plans[plan.id] = plan
        self._execution_locks[plan.id] = asyncio.Lock()

        try:
            plan.mark_running()
            logger.info(f"Starting execution of plan {plan.id}: {plan.goal[:50]}...")

            results = await self._execute(plan, on_progress, on_task_complete, on_task_fail)

            return results

        except asyncio.CancelledError:
            logger.info(f"Plan {plan.id} execution cancelled")
            plan.mark_cancelled()
            raise

        except Exception as e:
            logger.exception(f"Plan {plan.id} execution failed")
            plan.mark_failed()
            raise PlanExecutionError(
                str(e),
                plan_id=plan.id,
                details={"error_type": type(e).__name__},
            ) from e

        finally:
            # Cleanup
            del self._active_plans[plan.id]
            del self._execution_locks[plan.id]

    async def _execute(
        self,
        plan: Plan,
        on_progress: ProgressCallback | None,
        on_task_complete: TaskCallback | None,
        on_task_fail: TaskCallback | None,
    ) -> dict[str, Any]:
        """Internal execution loop."""
        results: dict[str, Any] = {
            "plan_id": plan.id,
            "goal": plan.goal,
            "completed_tasks": [],
            "failed_tasks": [],
            "cancelled_tasks": [],
            "outputs": {},
            "execution_summary": {},
        }

        # Check for timeout
        start_time = time.monotonic()

        try:
            while not plan.is_complete:
                # Check for timeout
                if self._check_timeout(start_time):
                    raise PlanExecutionError(
                        "Plan execution timeout",
                        plan_id=plan.id,
                    )

                # Check for cancellation
                if plan.status == PlanStatus.CANCELLED:
                    break

                # Get ready tasks
                ready_tasks = plan.get_ready_tasks_batch(
                    max_batch_size=self.config.max_concurrent_tasks
                )

                if not ready_tasks:
                    # Check for deadlock
                    pending = plan.get_pending_tasks()
                    if pending:
                        # Deadlock - tasks pending but none ready
                        for task in pending:
                            task.mark_failed("Unresolved dependencies (deadlock)")
                            results["failed_tasks"].append(task.id)
                            results["outputs"][task.id] = "Unresolved dependencies (deadlock)"

                            if on_task_fail:
                                on_task_fail(plan.id, task, TaskResult.failure_result("Deadlock"))

                        plan.mark_failed()
                        break
                    else:
                        # All tasks terminal
                        break

                # Execute ready tasks
                if self.config.enable_parallel_execution and len(ready_tasks) > 1:
                    # Execute in parallel
                    await self._execute_tasks_parallel(
                        plan,
                        ready_tasks,
                        results,
                        on_progress,
                        on_task_complete,
                        on_task_fail,
                    )
                else:
                    # Execute sequentially
                    for task in ready_tasks:
                        await self._execute_task(
                            plan,
                            task,
                            results,
                            on_progress,
                            on_task_complete,
                            on_task_fail,
                        )

                # Small yield to allow other operations
                await asyncio.sleep(0)

            # Determine final status
            if plan.status != PlanStatus.CANCELLED:
                if plan.all_succeeded:
                    plan.mark_completed()
                    results["status"] = "completed"
                else:
                    plan.mark_failed()
                    results["status"] = "failed"

            results["execution_summary"] = plan.execution_summary
            return results

        except asyncio.CancelledError:
            # Handle cancellation
            for task in plan.tasks.values():
                if not task.status.is_terminal:
                    task.mark_cancelled()
                    results["cancelled_tasks"].append(task.id)

            results["status"] = "cancelled"
            raise

    async def _execute_task(
        self,
        plan: Plan,
        task: Task,
        results: dict,
        on_progress: ProgressCallback | None,
        on_task_complete: TaskCallback | None,
        on_task_fail: TaskCallback | None,
    ) -> None:
        """Execute a single task."""
        task.mark_started()
        plan.current_task_id = task.id

        logger.info(f"Executing task {task.id}: {task.description[:50]}...")

        try:
            # Execute the task
            task_result = await self.task_executor.execute(task, plan)

            if task_result.success:
                task.mark_completed(task_result)
                results["completed_tasks"].append(task.id)
                results["outputs"][task.id] = task_result.output

                # Resolve dependencies
                plan.resolve_dependency(task.id)

                if on_task_complete:
                    on_task_complete(plan.id, task, task_result)

            else:
                # Handle failure
                await self._handle_task_failure(plan, task, task_result, results, on_task_fail)

        except TaskExecutionError as e:
            await self._handle_task_failure(
                plan,
                task,
                TaskResult.failure_result(str(e)),
                results,
                on_task_fail,
                can_retry=e.can_retry,
            )

        # Report progress
        if on_progress:
            completed, total, percentage = plan.progress
            on_progress(plan.id, task.id, percentage)

    async def _execute_tasks_parallel(
        self,
        plan: Plan,
        tasks: list[Task],
        results: dict,
        on_progress: ProgressCallback | None,
        on_task_complete: TaskCallback | None,
        on_task_fail: TaskCallback | None,
    ) -> None:
        """Execute multiple tasks in parallel."""

        # Create tasks for parallel execution
        async def execute_and_track(task: Task) -> None:
            await self._execute_task(
                plan, task, results, on_progress, on_task_complete, on_task_fail
            )

        # Execute all tasks concurrently
        await asyncio.gather(*[execute_and_track(t) for t in tasks])

    async def _handle_task_failure(
        self,
        plan: Plan,
        task: Task,
        result: TaskResult,
        results: dict,
        on_task_fail: TaskCallback | None,
        can_retry: bool = False,
    ) -> None:
        """Handle a task failure, potentially retrying."""
        error_msg = result.metadata.get("error", "Unknown error")

        if can_retry and task.retry_count < task.max_retries:
            # Retry
            task.retry_count += 1
            task.status = TaskStatus.PENDING
            task.error_message = None
            task.completed_at = None

            logger.info(f"Retrying task {task.id} (attempt {task.retry_count + 1})")

        else:
            # Mark as failed
            task.mark_failed(error_msg)
            results["failed_tasks"].append(task.id)
            results["outputs"][task.id] = error_msg

            # Resolve dependency to unblock dependent tasks
            # (they may fail later due to missing input)
            plan.resolve_dependency(task.id)

            if on_task_fail:
                on_task_fail(plan.id, task, result)

            # Check if we should stop on first error
            if self.config.stop_on_first_error:
                raise PlanExecutionError(
                    f"Task {task.id} failed: {error_msg}",
                    plan_id=plan.id,
                    failed_task_id=task.id,
                )

    def _check_timeout(self, start_time: float) -> bool:
        """Check if execution has exceeded timeout."""
        if self.config.timeout_seconds is None:
            return False

        elapsed = time.monotonic() - start_time
        return elapsed > self.config.timeout_seconds

    def get_plan_status(self, plan_id: str) -> Plan | None:
        """Get the current status of an active plan."""
        return self._active_plans.get(plan_id)

    def list_active_plans(self) -> list[str]:
        """List IDs of all active plans."""
        return list(self._active_plans.keys())

    async def pause_plan(self, plan_id: str) -> bool:
        """Pause a running plan.

        Args:
            plan_id: ID of the plan to pause

        Returns:
            True if the plan was paused, False otherwise

        Raises:
            PlanNotFoundError: If the plan is not active
        """
        plan = self._active_plans.get(plan_id)
        if not plan:
            raise PlanNotFoundError(plan_id)

        if plan.status != PlanStatus.RUNNING:
            return False

        plan.mark_paused()
        logger.info(f"Plan {plan_id} paused")
        return True

    async def resume_plan(
        self,
        plan_id: str,
        *,
        on_progress: ProgressCallback | None = None,
        on_task_complete: TaskCallback | None = None,
        on_task_fail: TaskCallback | None = None,
    ) -> dict[str, Any]:
        """Resume a paused plan.

        Args:
            plan_id: ID of the plan to resume
            on_progress: Optional progress callback
            on_task_complete: Optional task completion callback
            on_task_fail: Optional task failure callback

        Returns:
            Execution results

        Raises:
            PlanNotFoundError: If the plan is not active
            InvalidPlanStateError: If the plan is not in PAUSED state
        """
        plan = self._active_plans.get(plan_id)
        if not plan:
            raise PlanNotFoundError(plan_id)

        if plan.status != PlanStatus.PAUSED:
            raise InvalidPlanStateError(
                plan_id=plan_id,
                current_state=plan.status.name,
                required_state="PAUSED",
            )

        logger.info(f"Resuming plan {plan_id}")
        return await self._execute(plan, on_progress, on_task_complete, on_task_fail)

    async def cancel_plan(self, plan_id: str) -> bool:
        """Cancel an active plan.

        Args:
            plan_id: ID of the plan to cancel

        Returns:
            True if the plan was cancelled, False otherwise

        Raises:
            PlanNotFoundError: If the plan is not active
        """
        plan = self._active_plans.get(plan_id)
        if not plan:
            raise PlanNotFoundError(plan_id)

        if plan.status.is_terminal:
            return False

        plan.mark_cancelled()
        logger.info(f"Plan {plan_id} cancelled")
        return True


__all__ = [
    "PlanExecutor",
    "TaskExecutor",
    "ProgressCallback",
    "TaskCallback",
]
