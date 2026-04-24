"""Planning execution stage for chat pipeline."""

import logging
from typing import Any

from persona_agent.core.pipeline.context import ChatContext, StageResult
from persona_agent.core.planning import PlanningEngine
from persona_agent.core.planning.executor import PlanExecutor
from persona_agent.core.planning.models import Plan

logger = logging.getLogger(__name__)


class PlanningExecutionStage:
    """Handles complex requests using the planning system.

    If planning is enabled and the input requires multi-step execution,
    creates a plan, executes it, and formats results. Short-circuits
    the normal chat flow.
    """

    def __init__(
        self,
        planning_engine: PlanningEngine,
        plan_executor: PlanExecutor,
    ):
        self.planning_engine = planning_engine
        self.plan_executor = plan_executor
        self._active_plans: dict[str, Plan] = {}

    async def process(self, context: ChatContext) -> StageResult:
        if not context.enable_planning:
            return StageResult(context, should_continue=True)

        if not await self.planning_engine.should_plan(context.user_input):
            return StageResult(context, should_continue=True)

        # Execute planning flow
        response = await self._execute_planning(context)
        context.response = response
        context.is_complete = True
        return StageResult(context, should_continue=False)

    async def _execute_planning(self, context: ChatContext) -> str:
        """Internal planning execution logic."""
        logger.info(f"Using planning system for: {context.user_input[:50]}...")

        plan_context = {
            "session_id": context.session_id,
        }

        plan = await self.planning_engine.create_plan(context.user_input, plan_context)
        self._active_plans[plan.id] = plan

        try:
            results = await self.plan_executor.execute_plan(
                plan,
                on_progress=context.on_plan_progress,
            )
            return self._format_results(results)
        except Exception as e:
            logger.error(f"Plan execution failed: {e}")
            return f"I encountered an error while working on your request: {e}"
        finally:
            del self._active_plans[plan.id]

    def _format_results(self, results: dict[str, Any]) -> str:
        """Format plan execution results for user."""
        status = results.get("status", "unknown")

        if status == "completed":
            lines = ["I've completed your request. Here's what I did:"]
            for task_id in results.get("completed_tasks", []):
                output = results.get("outputs", {}).get(task_id, "")
                if output:
                    lines.append(f"\n**{task_id}**: {output[:300]}")
            return "\n".join(lines)

        elif status == "failed":
            lines = ["I encountered some issues while working on your request:"]
            for task_id in results.get("completed_tasks", []):
                output = results.get("outputs", {}).get(task_id, "")
                if output:
                    lines.append(f"✓ {task_id}: {output[:200]}...")
            for task_id in results.get("failed_tasks", []):
                error = results.get("outputs", {}).get(task_id, "Unknown error")
                lines.append(f"✗ {task_id}: {error[:100]}")
            return "\n".join(lines)

        return "Plan execution ended with unknown status."
