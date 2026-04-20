# Phase 1 Implementation Guide

Detailed implementation specifications for the three Phase 1 quick wins.

---

## 1. Planning System Foundation

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     User Input                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Intent Classifier (LLM)                        │
│  - Simple query (no plan needed)                            │
│  - Complex task (requires planning)                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
           ┌───────────┴────────────┐
           │                        │
           ▼                        ▼
┌──────────────────┐    ┌────────────────────────────┐
│ Direct Response  │    │ PlanningEngine             │
│ (existing flow)  │    │ - Decompose into tasks     │
└──────────────────┘    │ - Execute with state       │
                        │ - Handle failures          │
                        └─────────────┬──────────────┘
                                      │
                                      ▼
                        ┌────────────────────────────┐
                        │    Task Execution Loop     │
                        └────────────────────────────┘
```

### File Structure

```
src/persona_agent/core/
├── planning/
│   ├── __init__.py
│   ├── models.py          # Task, Plan, PlanStatus dataclasses
│   ├── engine.py          # PlanningEngine implementation
│   ├── executor.py        # PlanExecutor with state management
│   └── strategies.py      # Different planning strategies
```

### Core Models

```python
# src/persona_agent/core/planning/models.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Literal


class TaskStatus(Enum):
    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    BLOCKED = auto()  # Waiting for dependencies


class PlanStatus(Enum):
    CREATED = auto()
    RUNNING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    FAILED = auto()


@dataclass
class Task:
    """A single task within a plan."""

    id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    dependencies: list[str] = field(default_factory=list)
    result: Any = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    max_retries: int = 1
    retry_count: int = 0

    @property
    def is_ready(self) -> bool:
        """Check if all dependencies are satisfied."""
        return self.status == TaskStatus.PENDING and len(self.dependencies) == 0

    def mark_started(self) -> None:
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.now()

    def mark_completed(self, result: Any) -> None:
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.completed_at = datetime.now()

    def mark_failed(self, error: str) -> None:
        self.status = TaskStatus.FAILED
        self.error = error
        self.completed_at = datetime.now()


@dataclass
class Plan:
    """A plan consisting of multiple tasks."""

    id: str
    goal: str
    tasks: dict[str, Task] = field(default_factory=dict)
    status: PlanStatus = PlanStatus.CREATED
    context: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    current_task_id: str | None = None

    def add_task(self, task: Task) -> None:
        self.tasks[task.id] = task

    def get_ready_tasks(self) -> list[Task]:
        """Get all tasks that are ready to execute."""
        return [t for t in self.tasks.values() if t.is_ready]

    def get_task_order(self) -> list[str]:
        """Return topologically sorted task IDs."""
        # Simple topological sort
        visited: set[str] = set()
        order: list[str] = []

        def visit(task_id: str) -> None:
            if task_id in visited:
                return
            visited.add(task_id)
            task = self.tasks[task_id]
            for dep_id in task.dependencies:
                visit(dep_id)
            order.append(task_id)

        for task_id in self.tasks:
            visit(task_id)

        return order

    def resolve_dependency(self, completed_task_id: str) -> None:
        """Remove completed task from other tasks' dependencies."""
        for task in self.tasks.values():
            if completed_task_id in task.dependencies:
                task.dependencies.remove(completed_task_id)

    @property
    def is_complete(self) -> bool:
        """Check if all tasks are completed or failed."""
        return all(
            t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
            for t in self.tasks.values()
        )

    @property
    def progress(self) -> tuple[int, int]:
        """Return (completed_count, total_count)."""
        completed = sum(1 for t in self.tasks.values()
                       if t.status == TaskStatus.COMPLETED)
        return completed, len(self.tasks)
```

### Planning Engine

```python
# src/persona_agent/core/planning/engine.py

import json
import uuid
from typing import TYPE_CHECKING

from persona_agent.core.planning.models import Plan, Task, TaskStatus

if TYPE_CHECKING:
    from persona_agent.core.agent_engine import AgentEngine


class PlanningEngine:
    """Generate and manage execution plans."""

    PLANNING_PROMPT = """You are a task planning assistant. Given a user goal,
break it down into specific, actionable tasks.

Goal: {goal}

Context:
{context}

Provide your response as a JSON array of tasks. Each task should have:
- id: unique identifier (task_1, task_2, etc.)
- description: clear, specific action description
- dependencies: list of task IDs that must complete before this one (can be empty)

Example response:
[
  {
    "id": "task_1",
    "description": "Search for information about Python asyncio",
    "dependencies": []
  },
  {
    "id": "task_2",
    "description": "Summarize the key concepts found",
    "dependencies": ["task_1"]
  }
]

Tasks:"""

    def __init__(self, agent_engine: "AgentEngine"):
        self.agent_engine = agent_engine

    async def should_plan(self, user_input: str) -> bool:
        """Determine if user input requires a multi-step plan."""
        # Simple heuristic first
        planning_keywords = [
            "plan", "steps", "how to", "guide me", "help me",
            "create a", "build a", "research", "analyze",
        ]
        if any(kw in user_input.lower() for kw in planning_keywords):
            return True

        # Use LLM for classification
        prompt = f"""Does the following request require multiple steps to complete?

Request: "{user_input}"

Answer with just "yes" or "no"."""

        response = await self.agent_engine.llm_client.chat([
            {"role": "user", "content": prompt}
        ])

        return "yes" in response.content.lower()

    async def create_plan(self, goal: str, context: dict | None = None) -> Plan:
        """Generate a plan from a goal using LLM."""
        context_str = json.dumps(context, indent=2) if context else "No additional context"

        prompt = self.PLANNING_PROMPT.format(
            goal=goal,
            context=context_str
        )

        response = await self.agent_engine.llm_client.chat([
            {"role": "user", "content": prompt}
        ])

        # Parse task list from response
        try:
            task_data = json.loads(response.content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            task_data = json.loads(content.strip())

        plan = Plan(
            id=str(uuid.uuid4()),
            goal=goal,
            context=context or {}
        )

        for task_info in task_data:
            task = Task(
                id=task_info["id"],
                description=task_info["description"],
                dependencies=task_info.get("dependencies", [])
            )
            plan.add_task(task)

        return plan

    async def refine_plan(
        self,
        plan: Plan,
        failed_task: Task,
        error: str
    ) -> Plan:
        """Refine a plan when a task fails."""
        prompt = f"""A task in the plan failed. Help refine the plan.

Goal: {plan.goal}

Failed task: {failed_task.description}
Error: {error}

Current tasks:
{json.dumps([{"id": t.id, "desc": t.description, "status": t.status.name} for t in plan.tasks.values()], indent=2)}

Suggest alternative approach or additional tasks to handle this failure.
Return as JSON array of new/modified tasks."""

        response = await self.agent_engine.llm_client.chat([
            {"role": "user", "content": prompt}
        ])

        # Parse and update plan
        # Implementation details...

        return plan
```

### Plan Executor

```python
# src/persona_agent/core/planning/executor.py

import asyncio
import logging
from typing import TYPE_CHECKING

from persona_agent.core.planning.models import Plan, PlanStatus, Task, TaskStatus

if TYPE_CHECKING:
    from persona_agent.core.agent_engine import AgentEngine

logger = logging.getLogger(__name__)


class PlanExecutor:
    """Execute plans with state management and error handling."""

    def __init__(self, agent_engine: "AgentEngine"):
        self.agent_engine = agent_engine
        self.active_plans: dict[str, Plan] = {}

    async def execute_plan(
        self,
        plan: Plan,
        on_progress: callable | None = None
    ) -> dict:
        """Execute a plan to completion.

        Args:
            plan: The plan to execute
            on_progress: Callback(plan_id, task, progress_pct) for updates

        Returns:
            Execution results summary
        """
        plan.status = PlanStatus.RUNNING
        self.active_plans[plan.id] = plan

        results = {
            "plan_id": plan.id,
            "goal": plan.goal,
            "completed_tasks": [],
            "failed_tasks": [],
            "outputs": {}
        }

        try:
            while not plan.is_complete:
                ready_tasks = plan.get_ready_tasks()

                if not ready_tasks:
                    # Check for deadlocks (tasks remaining but none ready)
                    pending = [t for t in plan.tasks.values()
                              if t.status == TaskStatus.PENDING]
                    if pending:
                        # Deadlock - remaining tasks have unresolved dependencies
                        for task in pending:
                            task.mark_failed("Unresolved dependencies (deadlock)")
                            results["failed_tasks"].append(task.id)
                    break

                # Execute ready tasks (can be parallelized if independent)
                for task in ready_tasks[:3]:  # Limit concurrent tasks
                    await self._execute_task(plan, task, results, on_progress)

                # Small delay between iterations
                await asyncio.sleep(0.1)

            # Mark plan complete
            if all(t.status == TaskStatus.COMPLETED for t in plan.tasks.values()):
                plan.status = PlanStatus.COMPLETED
            else:
                plan.status = PlanStatus.FAILED

        except Exception as e:
            logger.exception("Plan execution failed")
            plan.status = PlanStatus.FAILED
            results["error"] = str(e)

        return results

    async def _execute_task(
        self,
        plan: Plan,
        task: Task,
        results: dict,
        on_progress: callable | None
    ) -> None:
        """Execute a single task."""
        task.mark_started()
        plan.current_task_id = task.id

        logger.info(f"Executing task {task.id}: {task.description}")

        try:
            # Build task context
            task_context = self._build_task_context(plan, task)

            # Use agent engine to execute
            response = await self.agent_engine.chat(
                user_input=task_context,
                stream=False
            )

            task.mark_completed(response)
            results["completed_tasks"].append(task.id)
            results["outputs"][task.id] = response

            # Update dependencies
            plan.resolve_dependency(task.id)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Task {task.id} failed: {error_msg}")

            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.PENDING  # Will be retried
                logger.info(f"Retrying task {task.id} (attempt {task.retry_count})")
            else:
                task.mark_failed(error_msg)
                results["failed_tasks"].append(task.id)
                plan.resolve_dependency(task.id)  # Unblock dependent tasks

        # Report progress
        if on_progress:
            completed, total = plan.progress
            pct = (completed / total * 100) if total > 0 else 0
            on_progress(plan.id, task, pct)

    def _build_task_context(self, plan: Plan, task: Task) -> str:
        """Build context for task execution."""
        lines = [
            f"Goal: {plan.goal}",
            f"Current task: {task.description}",
            "",
            "Previous results:"
        ]

        # Include results from completed dependencies
        for dep_id in task.dependencies:
            if dep_id in plan.tasks:
                dep_task = plan.tasks[dep_id]
                if dep_task.status == TaskStatus.COMPLETED:
                    lines.append(f"- {dep_task.description}: {dep_task.result}")

        if len(lines) == 3:  # No dependencies completed
            lines.append("(None - this is the first task)")

        lines.extend([
            "",
            "Execute this task and provide the result."
        ])

        return "\n".join(lines)

    def get_plan_status(self, plan_id: str) -> Plan | None:
        """Get current status of an active plan."""
        return self.active_plans.get(plan_id)

    async def pause_plan(self, plan_id: str) -> bool:
        """Pause a running plan."""
        plan = self.active_plans.get(plan_id)
        if plan and plan.status == PlanStatus.RUNNING:
            plan.status = PlanStatus.PAUSED
            return True
        return False

    async def resume_plan(self, plan_id: str) -> dict:
        """Resume a paused plan."""
        plan = self.active_plans.get(plan_id)
        if plan and plan.status == PlanStatus.PAUSED:
            plan.status = PlanStatus.RUNNING
            return await self.execute_plan(plan)
        return {"error": "Plan not found or not paused"}
```

### Integration with AgentEngine

```python
# Add to src/persona_agent/core/agent_engine.py

from persona_agent.core.planning.engine import PlanningEngine
from persona_agent.core.planning.executor import PlanExecutor

class AgentEngine:
    def __init__(self, ...):
        # ... existing init ...
        self.planning_engine = PlanningEngine(self)
        self.plan_executor = PlanExecutor(self)

    async def chat(
        self,
        user_input: str,
        stream: bool = False,
        enable_planning: bool = True
    ) -> str | AsyncIterator[str]:
        """Enhanced chat with optional planning."""

        # Check if planning is needed
        if enable_planning and await self.planning_engine.should_plan(user_input):
            # Generate and execute plan
            plan = await self.planning_engine.create_plan(
                goal=user_input,
                context={"current_persona": self.get_current_persona()}
            )

            results = await self.plan_executor.execute_plan(plan)

            # Format final response
            if results["failed_tasks"]:
                return self._format_plan_results_with_failures(results)
            return self._format_plan_results(results)

        # ... existing direct response flow ...

    def _format_plan_results(self, results: dict) -> str:
        """Format successful plan results for user."""
        lines = ["I've completed your request:"]
        for task_id in results["completed_tasks"]:
            output = results["outputs"].get(task_id, "")
            lines.append(f"\n**{task_id}**: {output[:200]}...")
        return "\n".join(lines)

    def _format_plan_results_with_failures(self, results: dict) -> str:
        """Format plan results with some failures."""
        lines = ["I completed most of your request, but encountered some issues:"]

        for task_id in results["completed_tasks"]:
            output = results["outputs"].get(task_id, "")
            lines.append(f"✓ {task_id}: {output[:100]}...")

        for task_id in results["failed_tasks"]:
            lines.append(f"✗ {task_id}: Failed")

        return "\n".join(lines)
```

### CLI Integration

```python
# Add to src/persona_agent/ui/cli.py

@cli.group()
def plan():
    """Plan management commands."""
    pass

@plan.command(name="create")
@click.argument("goal")
def plan_create(goal: str):
    """Create a new plan for a goal."""
    # Implementation

@plan.command(name="status")
@click.argument("plan_id")
def plan_status(plan_id: str):
    """Check plan execution status."""
    # Implementation

@plan.command(name="list")
def plan_list():
    """List active plans."""
    # Implementation
```

---

## 2. Skill Evolution System

### Architecture

```python
# src/persona_agent/skills/evolution.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import json


class EvolutionMode(Enum):
    """Modes for skill evolution."""

    # Fix bugs in existing skill
    FIX = "fix"

    # Create variant based on successful patterns
    DERIVED = "derived"

    # Capture entirely new skill from conversation
    CAPTURED = "captured"


@dataclass
class SkillExecution:
    """Record of a skill execution."""

    skill_name: str
    timestamp: datetime
    input_summary: str
    success: bool
    execution_time_ms: int
    user_feedback: str | None = None
    error_message: str | None = None


@dataclass
class SkillMetrics:
    """Aggregated metrics for a skill."""

    skill_name: str
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    avg_execution_time_ms: float = 0.0
    last_execution: datetime | None = None
    common_errors: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return self.successful_executions / self.total_executions

    @property
    def needs_improvement(self) -> bool:
        """Determine if skill needs evolution."""
        if self.total_executions < 5:
            return False  # Not enough data
        return self.success_rate < 0.7 or len(self.common_errors) > 2


class SkillEvolutionTracker:
    """Track skill performance and trigger evolution."""

    def __init__(self, storage_path: str = "./data/skill_evolution"):
        self.storage_path = storage_path
        self.execution_history: list[SkillExecution] = []
        self.metrics: dict[str, SkillMetrics] = {}

    def record_execution(
        self,
        skill_name: str,
        context: "SkillContext",
        result: "SkillResult",
        execution_time_ms: int
    ) -> None:
        """Record a skill execution."""
        execution = SkillExecution(
            skill_name=skill_name,
            timestamp=datetime.now(),
            input_summary=context.user_input[:100],
            success=result.success,
            execution_time_ms=execution_time_ms,
            error_message=result.data.get("error") if not result.success else None
        )

        self.execution_history.append(execution)
        self._update_metrics(skill_name, execution)

    def _update_metrics(self, skill_name: str, execution: SkillExecution) -> None:
        """Update aggregated metrics."""
        if skill_name not in self.metrics:
            self.metrics[skill_name] = SkillMetrics(skill_name=skill_name)

        metrics = self.metrics[skill_name]
        metrics.total_executions += 1
        metrics.last_execution = execution.timestamp

        if execution.success:
            metrics.successful_executions += 1
        else:
            metrics.failed_executions += 1
            if execution.error_message:
                metrics.common_errors.append(execution.error_message)

        # Update average execution time
        metrics.avg_execution_time_ms = (
            (metrics.avg_execution_time_ms * (metrics.total_executions - 1) +
             execution.execution_time_ms) / metrics.total_executions
        )

    async def evolve_skill(
        self,
        skill_name: str,
        mode: EvolutionMode,
        llm_client: Any
    ) -> str | None:
        """Generate evolved skill code.

        Returns:
            New skill code or None if evolution not possible
        """
        metrics = self.metrics.get(skill_name)
        if not metrics:
            return None

        # Get original skill code
        original_code = self._get_skill_source(skill_name)

        if mode == EvolutionMode.FIX:
            return await self._generate_fix(skill_name, original_code, metrics, llm_client)
        elif mode == EvolutionMode.DERIVED:
            return await self._generate_variant(skill_name, original_code, metrics, llm_client)
        elif mode == EvolutionMode.CAPTURED:
            return await self._generate_new_skill(skill_name, metrics, llm_client)

        return None

    async def _generate_fix(
        self,
        skill_name: str,
        original_code: str,
        metrics: SkillMetrics,
        llm_client: Any
    ) -> str:
        """Generate bug-fixed version of skill."""
        prompt = f"""Fix the bugs in this skill based on error reports.

Skill name: {skill_name}

Original code:
```python
{original_code}
```

Error reports:
{json.dumps(metrics.common_errors[-5:], indent=2)}

Success rate: {metrics.success_rate:.1%}

Provide the corrected Python code. Maintain the same class name and structure.
Only fix the bugs - don't change the skill's purpose."""

        response = await llm_client.chat([{"role": "user", "content": prompt}])

        # Extract code from response
        code = response.content
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0]
        elif "```" in code:
            code = code.split("```")[1].split("```")[0]

        return code.strip()

    async def _generate_variant(
        self,
        skill_name: str,
        original_code: str,
        metrics: SkillMetrics,
        llm_client: Any
    ) -> str:
        """Generate improved variant based on usage patterns."""
        # Get successful execution examples
        successes = [e for e in self.execution_history
                    if e.skill_name == skill_name and e.success][-5:]

        prompt = f"""Create an improved variant of this skill.

Original skill:
```python
{original_code}
```

Successful usage patterns:
{json.dumps([e.input_summary for e in successes], indent=2)}

Average execution time: {metrics.avg_execution_time_ms:.0f}ms

Create a variant that handles these patterns more efficiently.
Add the variant as a new class with suffix "V2".
"""

        response = await llm_client.chat([{"role": "user", "content": prompt}])

        # Extract code
        code = response.content
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0]
        elif "```" in code:
            code = code.split("```")[1].split("```")[0]

        return code.strip()

    def _get_skill_source(self, skill_name: str) -> str:
        """Get source code of a skill."""
        # Find skill class and get source
        from persona_agent.skills.registry import get_registry

        registry = get_registry()
        skill_class = registry.get_skill(skill_name)

        if skill_class:
            import inspect
            return inspect.getsource(skill_class)

        return ""


class EvolvedSkillManager:
    """Manage evolved skills lifecycle."""

    def __init__(self, evolution_dir: str = "./skills/evolved"):
        self.evolution_dir = evolution_dir
        self.approved_evolutions: dict[str, str] = {}  # name -> file_path

    async def propose_evolution(
        self,
        skill_name: str,
        new_code: str,
        reason: str
    ) -> str:
        """Propose a skill evolution for review.

        Returns:
            Proposal ID
        """
        proposal_id = f"{skill_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Save to pending directory
        pending_path = Path(self.evolution_dir) / "pending" / f"{proposal_id}.py"
        pending_path.parent.mkdir(parents=True, exist_ok=True)

        metadata = {
            "original_skill": skill_name,
            "proposal_id": proposal_id,
            "reason": reason,
            "proposed_at": datetime.now().isoformat()
        }

        content = f'"""Evolved skill proposal: {proposal_id}\n{json.dumps(metadata, indent=2)}\n"""\n\n{new_code}'
        pending_path.write_text(content)

        return proposal_id

    def approve_evolution(self, proposal_id: str) -> bool:
        """Approve and activate an evolved skill."""
        pending_path = Path(self.evolution_dir) / "pending" / f"{proposal_id}.py"
        approved_path = Path(self.evolution_dir) / "approved" / f"{proposal_id}.py"

        if not pending_path.exists():
            return False

        approved_path.parent.mkdir(parents=True, exist_ok=True)
        pending_path.rename(approved_path)

        self.approved_evolutions[proposal_id] = str(approved_path)

        # Load into registry
        from persona_agent.skills.registry import get_registry
        registry = get_registry()
        registry.discover_skills(approved_path.parent)

        return True

    def reject_evolution(self, proposal_id: str, reason: str) -> bool:
        """Reject an evolved skill proposal."""
        pending_path = Path(self.evolution_dir) / "pending" / f"{proposal_id}.py"
        rejected_path = Path(self.evolution_dir) / "rejected" / f"{proposal_id}.py"

        if not pending_path.exists():
            return False

        rejected_path.parent.mkdir(parents=True, exist_ok=True)

        # Add rejection reason to file
        content = pending_path.read_text()
        content += f'\n\n# REJECTION REASON: {reason}'

        rejected_path.write_text(content)
        pending_path.unlink()

        return True
```

---

## 3. Memory Compaction

### Implementation

```python
# src/persona_agent/core/memory_compaction.py

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from persona_agent.core.hierarchical_memory import HierarchicalMemory, EpisodicEntry


@dataclass
class CompactionResult:
    """Result of memory compaction."""

    original_count: int
    compacted_count: int
    summaries_created: int
    bytes_saved: int


class MemoryCompactor:
    """Compact old episodic memories into summaries."""

    def __init__(
        self,
        hierarchical_memory: "HierarchicalMemory",
        llm_client: Any | None = None
    ):
        self.memory = hierarchical_memory
        self.llm_client = llm_client

    async def compact_memories(
        self,
        older_than_days: int = 7,
        min_memories_per_group: int = 5,
        max_summary_length: int = 500
    ) -> CompactionResult:
        """Compact old memories into summaries.

        Strategy:
        1. Group memories by time window (e.g., daily)
        2. Generate summary for each group using LLM
        3. Store summary as new episodic memory with higher importance
        4. Mark original memories as compacted
        """
        cutoff_date = datetime.now() - timedelta(days=older_than_days)

        # Get memories older than cutoff
        old_memories = self._get_memories_older_than(cutoff_date)

        if len(old_memories) < min_memories_per_group:
            return CompactionResult(
                original_count=len(old_memories),
                compacted_count=0,
                summaries_created=0,
                bytes_saved=0
            )

        # Group by time window
        groups = self._group_by_time_window(old_memories, window_days=1)

        summaries_created = 0
        total_bytes_saved = 0

        for window, memories in groups.items():
            if len(memories) < min_memories_per_group:
                continue

            # Generate summary
            summary = await self._generate_summary(memories, max_summary_length)

            # Create summary memory with higher importance
            summary_entry = await self.memory.episodic.store_episode(
                content=summary,
                importance=0.8,  # Higher importance for summaries
                entities=self._extract_entities(memories),
                metadata={
                    "type": "compaction_summary",
                    "original_count": len(memories),
                    "window_start": window.isoformat(),
                    "compacted_at": datetime.now().isoformat()
                }
            )

            # Mark original memories as compacted
            for mem in memories:
                mem.metadata["compacted"] = True
                mem.metadata["summary_id"] = summary_entry.id
                total_bytes_saved += len(mem.content)

            summaries_created += 1

        return CompactionResult(
            original_count=len(old_memories),
            compacted_count=len(old_memories) - sum(
                1 for m in old_memories if not m.metadata.get("compacted")
            ),
            summaries_created=summaries_created,
            bytes_saved=total_bytes_saved
        )

    async def _generate_summary(
        self,
        memories: list["EpisodicEntry"],
        max_length: int
    ) -> str:
        """Generate a summary of multiple memories."""
        if not self.llm_client:
            # Fallback: simple concatenation with truncation
            contents = [m.content[:200] for m in memories]
            summary = " | ".join(contents)
            return summary[:max_length]

        # Use LLM to generate summary
        memory_texts = []
        for i, mem in enumerate(memories, 1):
            memory_texts.append(f"{i}. {mem.content}")

        prompt = f"""Summarize the following conversation memories into a concise summary.

Memories:
{"\n".join(memory_texts)}

Provide a brief summary (max {max_length} chars) capturing the key points and themes."""

        response = await self.llm_client.chat([{"role": "user", "content": prompt}])
        return response.content[:max_length]

    def _get_memories_older_than(self, cutoff: datetime) -> list["EpisodicEntry"]:
        """Get memories older than the cutoff date."""
        old_memories = []
        for entry in self.memory.episodic._episodes.values():
            if entry.timestamp < cutoff and not entry.metadata.get("compacted"):
                old_memories.append(entry)
        return sorted(old_memories, key=lambda m: m.timestamp)

    def _group_by_time_window(
        self,
        memories: list["EpisodicEntry"],
        window_days: int
    ) -> dict[datetime, list["EpisodicEntry"]]:
        """Group memories by time window."""
        from collections import defaultdict

        groups: dict[datetime, list] = defaultdict(list)

        for mem in memories:
            # Round to start of window
            days_since_epoch = mem.timestamp.toordinal()
            window_start = datetime.fromordinal(
                (days_since_epoch // window_days) * window_days
            )
            groups[window_start].append(mem)

        return groups

    def _extract_entities(self, memories: list["EpisodicEntry"]) -> list[str]:
        """Extract unique entities from memories."""
        entities: set[str] = set()
        for mem in memories:
            entities.update(mem.entities)
        return list(entities)


class AutoCompactionScheduler:
    """Schedule automatic compaction runs."""

    def __init__(
        self,
        compactor: MemoryCompactor,
        check_interval_hours: int = 24,
        memory_threshold: int = 1000
    ):
        self.compactor = compactor
        self.check_interval = check_interval_hours
        self.memory_threshold = memory_threshold
        self._last_check: datetime | None = None

    async def maybe_compact(self) -> CompactionResult | None:
        """Check if compaction is needed and run if so."""
        now = datetime.now()

        # Check if enough time has passed
        if self._last_check:
            hours_since_last = (now - self._last_check).total_seconds() / 3600
            if hours_since_last < self.check_interval:
                return None

        self._last_check = now

        # Check memory count
        memory_count = len(self.compactor.memory.episodic._episodes)
        if memory_count < self.memory_threshold:
            return None

        # Run compaction
        return await self.compactor.compact_memories()
```

---

## Testing Strategy

### Planning System Tests

```python
# tests/unit/core/planning/test_models.py

class TestTask:
    def test_task_is_ready_no_deps(self):
        task = Task(id="t1", description="Test task")
        assert task.is_ready

    def test_task_not_ready_with_deps(self):
        task = Task(id="t1", description="Test task", dependencies=["t0"])
        assert not task.is_ready

    def test_task_mark_completed(self):
        task = Task(id="t1", description="Test task")
        task.mark_completed("result")
        assert task.status == TaskStatus.COMPLETED
        assert task.result == "result"


class TestPlan:
    def test_get_ready_tasks(self):
        plan = Plan(id="p1", goal="Test goal")
        plan.add_task(Task(id="t1", description="Ready task"))
        plan.add_task(Task(id="t2", description="Blocked task", dependencies=["t1"]))

        ready = plan.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "t1"

    def test_resolve_dependency(self):
        plan = Plan(id="p1", goal="Test goal")
        plan.add_task(Task(id="t1", description="Task 1"))
        plan.add_task(Task(id="t2", description="Task 2", dependencies=["t1"]))

        plan.resolve_dependency("t1")
        assert plan.tasks["t2"].is_ready
```

### Skill Evolution Tests

```python
# tests/unit/skills/test_evolution.py

class TestSkillEvolutionTracker:
    def test_record_execution_updates_metrics(self):
        tracker = SkillEvolutionTracker()

        # Record successful execution
        tracker.record_execution(
            skill_name="test_skill",
            context=MagicMock(user_input="test"),
            result=SkillResult(success=True),
            execution_time_ms=100
        )

        metrics = tracker.metrics["test_skill"]
        assert metrics.total_executions == 1
        assert metrics.successful_executions == 1
        assert metrics.success_rate == 1.0

    def test_needs_improvement_detection(self):
        tracker = SkillEvolutionTracker()

        # Record 5 failures
        for _ in range(5):
            tracker.record_execution(
                skill_name="bad_skill",
                context=MagicMock(user_input="test"),
                result=SkillResult(success=False, data={"error": "Error 1"}),
                execution_time_ms=100
            )

        metrics = tracker.metrics["bad_skill"]
        assert metrics.needs_improvement
```

---

## Migration Guide

### Database Schema Changes

Add to session_repository or create new repository:

```python
# Add skill evolution table
CREATE TABLE skill_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    input_summary TEXT,
    success BOOLEAN NOT NULL,
    execution_time_ms INTEGER,
    error_message TEXT
);

CREATE INDEX idx_skill_executions_name ON skill_executions(skill_name);
CREATE INDEX idx_skill_executions_time ON skill_executions(timestamp);
```

### Configuration Updates

```python
# config.yaml additions
planning:
  enabled: true
  auto_detect: true
  max_concurrent_tasks: 3

evolution:
  enabled: true
  auto_propose: false  # Require manual approval
  min_executions_before_evolution: 5
  success_rate_threshold: 0.7

memory_compaction:
  enabled: true
  older_than_days: 7
  min_memories_per_group: 5
  check_interval_hours: 24
```
