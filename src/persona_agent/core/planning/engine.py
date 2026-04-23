"""Planning engine for creating and managing execution plans.

This module provides the PlanningEngine class which is responsible for:
- Determining if a user input requires planning
- Generating task decompositions using LLM
- Refining plans based on execution feedback
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any, Protocol

from persona_agent.core.planning.exceptions import PlanCreationError
from persona_agent.core.planning.models import Plan, PlanningConfig, Task, TaskStatus

if TYPE_CHECKING:
    from persona_agent.core.agent_engine import AgentEngine
    from persona_agent.utils.llm_client import LLMResponse

logger = logging.getLogger(__name__)


class LLMClientProtocol(Protocol):
    """Protocol for LLM client interactions."""

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
    ) -> LLMResponse: ...


class IntentClassifier:
    """Classifies user intent to determine if planning is needed."""

    # Keywords that suggest multi-step planning is beneficial
    PLANNING_KEYWORDS = frozenset(
        {
            "plan",
            "steps",
            "how to",
            "guide me",
            "help me",
            "create a",
            "build a",
            "research",
            "analyze",
            "find out",
            "investigate",
            "compare",
            "evaluate",
            "step by step",
            "walk me through",
            "process",
            "workflow",
            "procedure",
            "method",
            "strategy",
            "from scratch",
            "starting from",
            "begin with",
            "first then",
            "after that",
            "finally",
            "multiple",
            "several",
            "series of",
            "sequence",
        }
    )

    # Patterns that indicate simple queries (no planning needed)
    SIMPLE_PATTERNS = frozenset(
        {
            r"^hi\b",
            r"^hello\b",
            r"^hey\b",  # Greetings
            r"^good morning\b",
            r"^good afternoon\b",
            r"^good evening\b",  # Time-based greetings
            r"^what('s| is) your name",  # Identity questions
            r"^how are you",  # Status questions
            r"^thank",
            r"^thanks",  # Gratitude
            r"^bye\b",
            r"^goodbye",  # Farewells
            r"^[\?\.!]*$",  # Punctuation only
        }
    )

    def __init__(self, llm_client: LLMClientProtocol | None = None) -> None:
        self.llm_client = llm_client

    def heuristic_classify(self, user_input: str) -> bool | None:
        """Quick heuristic classification.

        Returns:
            True if planning likely needed, False if not, None if uncertain
        """
        input_lower = user_input.lower().strip()

        # Check simple patterns first
        for pattern in self.SIMPLE_PATTERNS:
            if re.search(pattern, input_lower, re.IGNORECASE):
                return False

        # Check for planning keywords
        words = set(input_lower.split())
        if words & self.PLANNING_KEYWORDS:
            return True

        # Check for complexity indicators
        if len(user_input) > 200:  # Longer inputs more likely need planning
            return True

        return None  # Uncertain, need LLM classification

    async def llm_classify(
        self,
        user_input: str,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """Use LLM to classify if planning is needed.

        This is more accurate but slower than heuristic classification.
        """
        if not self.llm_client:
            # Default to no planning if no LLM available
            return False

        system_prompt = """You are an intent classifier for an AI assistant.
Your job is to determine if a user request requires multiple steps to complete.

Answer TRUE if the request:
- Requires research or information gathering
- Involves multiple distinct actions
- Needs step-by-step execution
- Would benefit from planning before execution

Answer FALSE if the request:
- Is a simple greeting or farewell
- Asks a straightforward question
- Requests a simple, single-action task
- Is social/conversational

Respond with ONLY "TRUE" or "FALSE".
Do not explain your reasoning."""

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f'Request: "{user_input}"\n\nDoes this require multiple steps?',
            },
        ]

        try:
            response = await self.llm_client.chat(messages, temperature=0.0)
            result = response.content.strip().upper()
            return "TRUE" in result
        except Exception as e:
            logger.warning(f"LLM classification failed: {e}")
            return False

    async def classify(
        self,
        user_input: str,
        context: dict[str, Any] | None = None,
        use_llm: bool = True,
    ) -> bool:
        """Classify if planning is needed.

        Uses heuristic first, falls back to LLM if uncertain.
        """
        # Try heuristic first
        heuristic_result = self.heuristic_classify(user_input)

        if heuristic_result is not None:
            logger.debug(
                f"Heuristic classification: planning={'needed' if heuristic_result else 'not needed'}"
            )
            return heuristic_result

        # Fall back to LLM if available and allowed
        if use_llm and self.llm_client:
            return await self.llm_classify(user_input, context)

        # Default to no planning if uncertain and no LLM
        return False


class TaskDecomposer:
    """Decomposes goals into tasks using LLM."""

    PLANNING_PROMPT_TEMPLATE = """You are a task planning assistant. Your job is to break down a goal into specific, actionable tasks.

Goal: {goal}

Context:
{context}

Instructions:
1. Break down the goal into 2-10 concrete, actionable tasks
2. Each task should be specific and achievable
3. Consider dependencies between tasks
4. Order tasks logically (dependencies first)

Provide your response as a JSON object with the following structure:
{{
  "tasks": [
    {{
      "id": "task_1",
      "description": "Clear, specific action description",
      "dependencies": []  // IDs of tasks that must complete first
    }},
    {{
      "id": "task_2",
      "description": "Another specific action",
      "dependencies": ["task_1"]  // Depends on task_1
    }}
  ],
  "reasoning": "Brief explanation of your task breakdown"
}}

Requirements:
- Task IDs should be unique (task_1, task_2, etc.)
- Descriptions should be clear and actionable
- Dependencies must reference valid task IDs
- A task can depend on multiple previous tasks"""

    def __init__(self, llm_client: LLMClientProtocol) -> None:
        self.llm_client = llm_client

    async def decompose(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> list[Task]:
        """Decompose a goal into tasks.

        Args:
            goal: The goal to decompose
            context: Additional context for planning

        Returns:
            List of Task objects

        Raises:
            PlanCreationError: If decomposition fails
        """
        context_str = self._format_context(context)

        prompt = self.PLANNING_PROMPT_TEMPLATE.format(
            goal=goal,
            context=context_str,
        )

        messages = [
            {"role": "system", "content": "You are a precise task planning assistant."},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.llm_client.chat(messages, temperature=0.3)
            return self._parse_tasks(response.content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            raise PlanCreationError(
                f"Failed to parse task decomposition: {e}",
                details={"response": response.content if "response" in locals() else None},
            ) from e
        except Exception as e:
            logger.exception("Task decomposition failed")
            raise PlanCreationError(f"Failed to decompose goal: {e}") from e

    def _format_context(self, context: dict[str, Any] | None) -> str:
        """Format context for the prompt."""
        if not context:
            return "No additional context provided."

        lines = []
        for key, value in context.items():
            if isinstance(value, dict):
                lines.append(f"{key}:")
                for k, v in value.items():
                    lines.append(f"  - {k}: {v}")
            else:
                lines.append(f"{key}: {value}")

        return "\n".join(lines) if lines else "No additional context provided."

    def _parse_tasks(self, content: str) -> list[Task]:
        """Parse tasks from LLM response.

        Handles various formats including markdown code blocks.
        """
        # Extract JSON from markdown code blocks if present
        json_content = self._extract_json(content)

        data = json.loads(json_content)

        if "tasks" not in data:
            raise PlanCreationError("Response missing 'tasks' key")

        tasks = []
        for task_data in data["tasks"]:
            task = Task(
                id=task_data["id"],
                description=task_data["description"],
                dependencies=task_data.get("dependencies", []),
                status=TaskStatus.PENDING,
            )
            tasks.append(task)

        # Validate dependencies
        task_ids = {t.id for t in tasks}
        for task in tasks:
            for dep_id in task.dependencies:
                if dep_id not in task_ids:
                    logger.warning(f"Task {task.id} has unresolved dependency: {dep_id}")

        return tasks

    def _extract_json(self, content: str) -> str:
        """Extract JSON from content that may be wrapped in markdown."""
        # Try code blocks first
        for pattern in [r"```json\s*(.*?)\s*```", r"```\s*(.*?)\s*```"]:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                return match.group(1).strip()

        # Try to find JSON object directly
        match = re.search(r"(\{[\s\S]*\})", content)
        if match:
            return match.group(1).strip()

        return content.strip()


class PlanRefiner:
    """Refines plans based on execution feedback."""

    REFINEMENT_PROMPT_TEMPLATE = """A task in a plan failed. Help refine the plan to handle this failure.

Original Goal: {goal}

Failed Task:
- ID: {task_id}
- Description: {task_description}
- Error: {error}

Current Plan Status:
{plan_status}

Suggest one of the following approaches:
1. Add an alternative task to try a different approach
2. Break the failed task into smaller subtasks
3. Modify existing tasks to avoid the failure

Provide your response as JSON:
{{
  "approach": "alternative|subtask|modify",
  "reasoning": "Why this approach",
  "new_tasks": [
    // Only include new or modified tasks
  ],
  "modify_tasks": [
    // Tasks to modify with their new descriptions
  ]
}}"""

    def __init__(self, llm_client: LLMClientProtocol) -> None:
        self.llm_client = llm_client

    async def refine(
        self,
        plan: Plan,
        failed_task_id: str,
        error: str,
    ) -> list[Task]:
        """Generate new tasks to handle a failure.

        Args:
            plan: The current plan
            failed_task_id: ID of the failed task
            error: Error message

        Returns:
            List of new tasks to add to the plan
        """
        failed_task = plan.tasks.get(failed_task_id)
        if not failed_task:
            raise ValueError(f"Task {failed_task_id} not found in plan")

        plan_status = self._format_plan_status(plan)

        prompt = self.REFINEMENT_PROMPT_TEMPLATE.format(
            goal=plan.goal,
            task_id=failed_task_id,
            task_description=failed_task.description,
            error=error,
            plan_status=plan_status,
        )

        messages = [
            {"role": "system", "content": "You are a plan refinement assistant."},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.llm_client.chat(messages, temperature=0.3)
            return self._parse_refinement(response.content, failed_task_id)
        except Exception as e:
            logger.warning(f"Plan refinement failed: {e}")
            return []

    def _format_plan_status(self, plan: Plan) -> str:
        """Format plan status for the prompt."""
        lines = []
        for task in plan.tasks.values():
            status_symbol = {
                TaskStatus.COMPLETED: "✓",
                TaskStatus.FAILED: "✗",
                TaskStatus.IN_PROGRESS: "→",
            }.get(task.status, "○")
            lines.append(f"{status_symbol} {task.id}: {task.description}")
        return "\n".join(lines)

    def _parse_refinement(self, content: str, failed_task_id: str) -> list[Task]:
        """Parse refinement response into new tasks."""
        json_content = self._extract_json(content)
        data = json.loads(json_content)

        new_tasks: list[Task] = []

        # Add new tasks
        for task_data in data.get("new_tasks", []):
            task = Task(
                id=task_data["id"],
                description=task_data["description"],
                dependencies=task_data.get("dependencies", [failed_task_id]),
            )
            new_tasks.append(task)

        return new_tasks

    def _extract_json(self, content: str) -> str:
        """Extract JSON from content."""
        for pattern in [r"```json\s*(.*?)\s*```", r"```\s*(.*?)\s*```"]:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                return match.group(1).strip()

        match = re.search(r"(\{[\s\S]*\})", content)
        if match:
            return match.group(1).strip()

        return content.strip()


class PlanningEngine:
    """Main engine for creating and refining plans.

    The planning engine coordinates intent classification, task decomposition,
    and plan refinement. It integrates with the agent engine for execution.

    Example:
        engine = PlanningEngine(agent_engine, config)

        # Check if planning is needed
        if await engine.should_plan("Research Python async patterns"):
            plan = await engine.create_plan("Research Python async patterns")
            # Execute plan...
    """

    def __init__(
        self,
        agent_engine: AgentEngine | None = None,
        config: PlanningConfig | None = None,
    ) -> None:
        """Initialize the planning engine.

        Args:
            agent_engine: The agent engine for LLM access and execution
            config: Planning configuration
        """
        self.agent_engine = agent_engine
        self.config = config or PlanningConfig()

        # Initialize components
        llm_client = self._get_llm_client()
        self.classifier = IntentClassifier(llm_client)
        self.decomposer = TaskDecomposer(llm_client) if llm_client else None
        self.refiner = PlanRefiner(llm_client) if llm_client else None

    def _get_llm_client(self) -> LLMClientProtocol | None:
        """Get LLM client from agent engine or return None."""
        if self.agent_engine and hasattr(self.agent_engine, "llm_client"):
            client = self.agent_engine.llm_client
            if client is not None:
                return client  # type: ignore[return-value]
        return None

    async def should_plan(
        self,
        user_input: str,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """Determine if user input requires a multi-step plan.

        Uses a two-tier approach:
        1. Fast heuristic classification
        2. LLM-based classification if uncertain

        Args:
            user_input: The user's request
            context: Additional context for classification

        Returns:
            True if planning should be used
        """
        if not self.config.enabled:
            return False

        if not self.config.auto_detect:
            return False

        return await self.classifier.classify(
            user_input,
            context,
            use_llm=True,
        )

    async def create_plan(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> Plan:
        """Create a plan from a goal.

        Args:
            goal: The high-level goal to achieve
            context: Additional context for planning

        Returns:
            A new Plan with decomposed tasks

        Raises:
            PlanCreationError: If plan creation fails
            RuntimeError: If no LLM client is available
        """
        if not self.decomposer:
            raise RuntimeError("No LLM client available for plan creation")

        logger.info(f"Creating plan for goal: {goal[:100]}...")

        # Generate tasks
        tasks = await self.decomposer.decompose(goal, context)

        if not tasks:
            raise PlanCreationError("No tasks generated for goal")

        # Create plan
        plan_id = f"plan_{id(goal)}_{hash(goal) & 0xFFFFFFFF:08x}"
        plan = Plan(
            id=plan_id,
            goal=goal,
            context=context or {},
        )

        for task in tasks:
            plan.add_task(task)

        logger.info(f"Created plan {plan.id} with {len(tasks)} tasks")
        return plan

    async def refine_plan(
        self,
        plan: Plan,
        failed_task_id: str,
        error: str,
    ) -> Plan:
        """Refine a plan after a task failure.

        Args:
            plan: The plan to refine
            failed_task_id: ID of the failed task
            error: Error message

        Returns:
            Updated plan with additional tasks
        """
        if not self.refiner:
            logger.warning("No refiner available, returning original plan")
            return plan

        logger.info(f"Refining plan {plan.id} after failure in task {failed_task_id}")

        new_tasks = await self.refiner.refine(plan, failed_task_id, error)

        for task in new_tasks:
            plan.add_task(task)
            logger.debug(f"Added refinement task: {task.id}")

        return plan

    def set_llm_client(self, llm_client: LLMClientProtocol) -> None:
        """Set or update the LLM client.

        This is useful for reconfiguring the engine after initialization.
        """
        self.classifier.llm_client = llm_client
        self.decomposer = TaskDecomposer(llm_client)
        self.refiner = PlanRefiner(llm_client)


__all__ = [
    "PlanningEngine",
    "IntentClassifier",
    "TaskDecomposer",
    "PlanRefiner",
    "LLMClientProtocol",
]
