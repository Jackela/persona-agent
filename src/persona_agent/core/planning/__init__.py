"""Planning system for persona-agent.

This module provides comprehensive task planning capabilities including:
- Intent classification to determine if planning is needed
- LLM-based task decomposition
- Plan execution with dependency management
- Parallel task execution
- Progress tracking and callbacks

Example:
    from persona_agent.core.planning import PlanningEngine, PlanExecutor

    # Create and configure
    engine = PlanningEngine(agent_engine)
    executor = PlanExecutor(agent_engine)

    # Check if planning is needed
    if await engine.should_plan("Research Python async patterns"):
        plan = await engine.create_plan("Research Python async patterns")

        # Execute with progress tracking
        def on_progress(plan_id, task_id, pct):
            print(f"Progress: {pct}%")

        results = await executor.execute_plan(plan, on_progress=on_progress)
"""

from persona_agent.core.planning.engine import (
    IntentClassifier,
    LLMClientProtocol,
    PlanningEngine,
    PlanRefiner,
    TaskDecomposer,
)
from persona_agent.core.planning.exceptions import (
    CyclicDependencyError,
    DependencyError,
    InvalidPlanStateError,
    PlanCreationError,
    PlanExecutionError,
    PlanningConfigError,
    PlanningError,
    PlanNotFoundError,
    TaskExecutionError,
)
from persona_agent.core.planning.executor import (
    PlanExecutor,
    ProgressCallback,
    TaskCallback,
    TaskExecutor,
)
from persona_agent.core.planning.models import (
    ExecutionConfig,
    Plan,
    PlanningConfig,
    PlanStatus,
    Task,
    TaskResult,
    TaskStatus,
)

__version__ = "1.0.0"

__all__ = [
    # Engine
    "PlanningEngine",
    "IntentClassifier",
    "TaskDecomposer",
    "PlanRefiner",
    "LLMClientProtocol",
    # Executor
    "PlanExecutor",
    "TaskExecutor",
    "ProgressCallback",
    "TaskCallback",
    # Models
    "Plan",
    "Task",
    "TaskResult",
    "PlanStatus",
    "TaskStatus",
    "PlanningConfig",
    "ExecutionConfig",
    # Exceptions
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
