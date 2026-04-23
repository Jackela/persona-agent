"""Planning system configuration schemas.

This module defines the configuration structures for the planning system,
including task execution, intent classification, and retry policies.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class RetryConfig(BaseModel):
    """Retry policy configuration for failed tasks.

    Attributes:
        max_attempts: Maximum number of retry attempts
        base_delay_seconds: Initial delay between retries
        max_delay_seconds: Maximum delay between retries
        exponential_base: Multiplier for exponential backoff
        retryable_exceptions: Exception types that should trigger retry
    """

    max_attempts: int = Field(default=3, ge=1, le=10)
    base_delay_seconds: float = Field(default=1.0, ge=0.1)
    max_delay_seconds: float = Field(default=60.0, ge=1.0)
    exponential_base: float = Field(default=2.0, ge=1.0)
    retryable_exceptions: list[str] = Field(
        default_factory=lambda: [
            "persona_agent.core.planning.exceptions.TaskExecutionError",
            "persona_agent.core.planning.exceptions.DependencyError",
        ]
    )


class ParallelExecutionConfig(BaseModel):
    """Parallel execution configuration.

    Attributes:
        enabled: Whether parallel execution is enabled
        max_workers: Maximum number of concurrent workers
        max_concurrent_tasks: Maximum tasks to execute in parallel
    """

    enabled: bool = True
    max_workers: int = Field(default=4, ge=1, le=16)
    max_concurrent_tasks: int = Field(default=8, ge=1, le=32)


class IntentClassificationConfig(BaseModel):
    """Intent classification configuration.

    Attributes:
        use_llm: Whether to use LLM for intent classification
        heuristic_priority: Priority of heuristic rules (0-1)
        llm_model: Model to use for LLM classification
        cache_classifications: Whether to cache classification results
        cache_ttl_seconds: Cache time-to-live in seconds
    """

    use_llm: bool = True
    heuristic_priority: float = Field(default=0.3, ge=0.0, le=1.0)
    llm_model: str | None = None
    cache_classifications: bool = True
    cache_ttl_seconds: int = Field(default=300, ge=60)


class TaskDecompositionConfig(BaseModel):
    """Task decomposition configuration.

    Attributes:
        max_tasks_per_plan: Maximum number of tasks in a single plan
        min_task_granularity: Minimum task size (in estimated seconds)
        allow_parallel_subtasks: Whether subtasks can run in parallel
        require_explicit_dependencies: Whether dependencies must be explicit
    """

    max_tasks_per_plan: int = Field(default=20, ge=5, le=100)
    min_task_granularity: int = Field(default=5, ge=1, le=300)
    allow_parallel_subtasks: bool = True
    require_explicit_dependencies: bool = False


class PlanningSystemConfig(BaseModel):
    """Complete planning system configuration.

    This schema defines all configuration options for the planning system,
    including execution, classification, and retry policies.

    Example:
        ```yaml
        planning:
          execution:
            enable_parallel_execution: true
            max_concurrent_tasks: 8
          retry:
            max_attempts: 3
            base_delay_seconds: 1.0
          intent_classification:
            use_llm: true
            heuristic_priority: 0.3
        ```
    """

    enabled: bool = True
    execution: ParallelExecutionConfig = Field(default_factory=ParallelExecutionConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    intent_classification: IntentClassificationConfig = Field(
        default_factory=IntentClassificationConfig
    )
    task_decomposition: TaskDecompositionConfig = Field(default_factory=TaskDecompositionConfig)

    @field_validator("execution", mode="before")
    @classmethod
    def validate_execution(
        cls, v: dict | ParallelExecutionConfig | None
    ) -> ParallelExecutionConfig:
        """Handle both dict and object inputs."""
        if v is None:
            return ParallelExecutionConfig()
        if isinstance(v, ParallelExecutionConfig):
            return v
        return ParallelExecutionConfig(**v)

    @field_validator("retry", mode="before")
    @classmethod
    def validate_retry(cls, v: dict | RetryConfig | None) -> RetryConfig:
        """Handle both dict and object inputs."""
        if v is None:
            return RetryConfig()
        if isinstance(v, RetryConfig):
            return v
        return RetryConfig(**v)

    @field_validator("intent_classification", mode="before")
    @classmethod
    def validate_intent_classification(
        cls, v: dict | IntentClassificationConfig | None
    ) -> IntentClassificationConfig:
        """Handle both dict and object inputs."""
        if v is None:
            return IntentClassificationConfig()
        if isinstance(v, IntentClassificationConfig):
            return v
        return IntentClassificationConfig(**v)

    @field_validator("task_decomposition", mode="before")
    @classmethod
    def validate_task_decomposition(
        cls, v: dict | TaskDecompositionConfig | None
    ) -> TaskDecompositionConfig:
        """Handle both dict and object inputs."""
        if v is None:
            return TaskDecompositionConfig()
        if isinstance(v, TaskDecompositionConfig):
            return v
        return TaskDecompositionConfig(**v)


__all__ = [
    "PlanningSystemConfig",
    "RetryConfig",
    "ParallelExecutionConfig",
    "IntentClassificationConfig",
    "TaskDecompositionConfig",
]
