"""Unified exception hierarchy for Persona Agent.

All application-specific exceptions inherit from :class:`PersonaAgentError`,
allowing callers to catch every custom error in a single ``except`` block while
still supporting fine-grained handling via subclasses.

Example::

    try:
        ...
    except PlanningError:
        ...  # handle planning issues
    except MemoryError:
        ...  # handle memory issues
    except PersonaAgentError:
        ...  # catch-all for any application error
"""

from __future__ import annotations


class PersonaAgentError(Exception):
    """Base exception for ALL application errors.

    Parameters
    ----------
    message:
        Human-readable error description.
    code:
        Machine-readable error code (default: ``"UNKNOWN_ERROR"``).
    details:
        Arbitrary key/value context for debugging / logging.
    recoverable:
        Whether the caller may reasonably retry the operation.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str = "UNKNOWN_ERROR",
        details: dict | None = None,
        recoverable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.recoverable = recoverable

    def __str__(self) -> str:
        if self.details:
            return f"[{self.code}] {self.message} - Details: {self.details}"
        return f"[{self.code}] {self.message}"


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------

class PlanningError(PersonaAgentError):
    """Base exception for all planning-related errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "PLANNING_ERROR",
        details: dict | None = None,
        recoverable: bool = False,
    ) -> None:
        super().__init__(message, code=code, details=details, recoverable=recoverable)


class PlanCreationError(PlanningError):
    """Raised when plan creation fails."""

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message, code="PLAN_CREATION_ERROR", details=details)


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
        super().__init__(message, code="PLAN_EXECUTION_ERROR", details=details)
        self.plan_id = plan_id
        self.failed_task_id = failed_task_id


class TaskExecutionError(PlanningError):
    """Raised when an individual task fails execution."""

    def __init__(
        self,
        message: str,
        *,
        task_id: str,
        attempt: int = 1,
        max_retries: int = 1,
        details: dict | None = None,
    ) -> None:
        super().__init__(message, code="TASK_EXECUTION_ERROR", details=details)
        self.task_id = task_id
        self.attempt = attempt
        self.max_retries = max_retries
        self.can_retry = attempt < max_retries


class DependencyError(PlanningError):
    """Raised when task dependencies cannot be satisfied."""

    def __init__(
        self,
        message: str,
        *,
        task_id: str,
        unresolved_dependencies: list[str],
    ) -> None:
        super().__init__(message, code="DEPENDENCY_ERROR")
        self.task_id = task_id
        self.unresolved_dependencies = unresolved_dependencies


class CyclicDependencyError(DependencyError):
    """Raised when a circular dependency is detected in the task graph."""

    def __init__(self, *, cycle_path: list[str]) -> None:
        message = f"Circular dependency detected: {' -> '.join(cycle_path)}"
        super().__init__(
            message,
            task_id=cycle_path[0],
            unresolved_dependencies=cycle_path,
        )
        self.cycle_path = cycle_path


class PlanNotFoundError(PlanningError):
    """Raised when attempting to access a non-existent plan."""

    def __init__(self, plan_id: str) -> None:
        super().__init__(f"Plan not found: {plan_id}", code="PLAN_NOT_FOUND")
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
            f"but required state is one of: {states}",
            code="INVALID_PLAN_STATE",
        )
        self.plan_id = plan_id
        self.current_state = current_state
        self.required_states = states


class PlanningConfigError(PlanningError):
    """Raised when planning configuration is invalid."""

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message, code="PLANNING_CONFIG_ERROR", details=details)


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------

class MemoryError(PersonaAgentError):
    """Base exception for memory-related errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "MEMORY_ERROR",
        details: dict | None = None,
        recoverable: bool = False,
    ) -> None:
        super().__init__(message, code=code, details=details, recoverable=recoverable)


class CompactionError(MemoryError):
    """Raised when memory compaction fails."""

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message, code="COMPACTION_ERROR", details=details)


class SummarizationError(CompactionError):
    """Raised when LLM summarization fails."""

    def __init__(
        self,
        message: str,
        *,
        memory_count: int | None = None,
        prompt_length: int | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.code = "SUMMARIZATION_ERROR"
        self.memory_count = memory_count
        self.prompt_length = prompt_length


class MemoryGroupError(CompactionError):
    """Raised when memory grouping fails."""

    def __init__(
        self,
        message: str,
        *,
        group_date: str | None = None,
        memory_count: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = "MEMORY_GROUP_ERROR"
        self.group_date = group_date
        self.memory_count = memory_count


class SchedulerError(MemoryError):
    """Raised when compaction scheduling fails."""

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message, code="SCHEDULER_ERROR", details=details)


class MemoryConfigurationError(MemoryError):
    """Raised when memory configuration is invalid."""

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message, code="MEMORY_CONFIGURATION_ERROR", details=details)


class MemoryStoreError(MemoryError):
    """Error in memory store operations."""

    def __init__(
        self,
        message: str,
        *,
        operation: str | None = None,
        details: dict | None = None,
        **kwargs,
    ) -> None:
        merged = details or {}
        if operation:
            merged["operation"] = operation
        merged.update(kwargs)
        super().__init__(message, code="MEMORY_ERROR", details=merged)
        self.operation = operation


class UserNotFoundError(MemoryError):
    """Requested user not found in memory store."""

    def __init__(self, user_id: str, *, details: dict | None = None) -> None:
        merged = details or {}
        merged["user_id"] = user_id
        merged.setdefault("operation", "get_user")
        super().__init__(
            f"User not found: {user_id}",
            code="USER_NOT_FOUND",
            details=merged,
        )
        self.user_id = user_id


class ConversationNotFoundError(MemoryError):
    """Requested conversation not found."""

    def __init__(self, conversation_id: str, *, details: dict | None = None) -> None:
        merged = details or {}
        merged["conversation_id"] = conversation_id
        merged.setdefault("operation", "get_conversation")
        super().__init__(
            f"Conversation not found: {conversation_id}",
            code="CONVERSATION_NOT_FOUND",
            details=merged,
        )
        self.conversation_id = conversation_id


# ---------------------------------------------------------------------------
# Tools / Skills
# ---------------------------------------------------------------------------

class ToolError(PersonaAgentError):
    """Base exception for tool/skill execution errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "TOOL_ERROR",
        details: dict | None = None,
        recoverable: bool = False,
    ) -> None:
        super().__init__(message, code=code, details=details, recoverable=recoverable)


class SkillError(ToolError):
    """Error in skill system."""

    def __init__(
        self,
        message: str,
        *,
        skill_name: str | None = None,
        details: dict | None = None,
    ) -> None:
        merged = details or {}
        if skill_name:
            merged["skill_name"] = skill_name
        super().__init__(message, code="SKILL_ERROR", details=merged)
        self.skill_name = skill_name


class SkillNotFoundError(SkillError):
    """Requested skill not found in registry."""

    def __init__(self, skill_name: str, *, details: dict | None = None) -> None:
        merged = details or {}
        merged["skill_name"] = skill_name
        super().__init__(
            f"Skill not found: {skill_name}",
            details=merged,
        )
        self.code = "SKILL_NOT_FOUND"
        self.skill_name = skill_name


class SkillExecutionError(SkillError):
    """Error executing a skill."""

    def __init__(
        self,
        skill_name: str,
        original_error: Exception,
        *,
        details: dict | None = None,
        **kwargs,
    ) -> None:
        merged = details or {}
        merged["skill_name"] = skill_name
        merged["original_error_type"] = type(original_error).__name__
        merged.update(kwargs)
        super().__init__(
            f"Error executing skill '{skill_name}': {original_error}",
            details=merged,
        )
        self.code = "SKILL_EXECUTION_ERROR"
        self.original_error = original_error


# ---------------------------------------------------------------------------
# Evolution
# ---------------------------------------------------------------------------

class EvolutionError(PersonaAgentError):
    """Base exception for skill evolution errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "EVOLUTION_ERROR",
        details: dict | None = None,
        recoverable: bool = False,
    ) -> None:
        super().__init__(message, code=code, details=details, recoverable=recoverable)


class TrackingError(EvolutionError):
    """Raised when skill tracking fails."""

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message, code="TRACKING_ERROR", details=details)


class GenerationError(EvolutionError):
    """Raised when evolution generation fails."""

    def __init__(
        self,
        message: str,
        *,
        skill_name: str | None = None,
        mode: str | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(message, code="GENERATION_ERROR", details=details)
        self.skill_name = skill_name
        self.mode = mode


class ProposalError(EvolutionError):
    """Raised when proposal management fails."""

    def __init__(
        self,
        message: str,
        *,
        proposal_id: str | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(message, code="PROPOSAL_ERROR", details=details)
        self.proposal_id = proposal_id


class InvalidEvolutionModeError(EvolutionError):
    """Raised when an invalid evolution mode is specified."""

    def __init__(self, mode: str, *, details: dict | None = None) -> None:
        super().__init__(
            f"Invalid evolution mode: {mode}",
            code="INVALID_EVOLUTION_MODE",
            details=details,
        )
        self.mode = mode


class EvolutionValidationError(EvolutionError):
    """Raised when evolved skill validation fails."""

    def __init__(
        self,
        message: str,
        *,
        errors: list[str] | None = None,
        details: dict | None = None,
    ) -> None:
        merged = details or {}
        if errors:
            merged["errors"] = errors
        super().__init__(message, code="EVOLUTION_VALIDATION_ERROR", details=merged)
        self.errors = errors or []


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class ConfigError(PersonaAgentError):
    """Error in configuration files or settings."""

    def __init__(
        self,
        message: str,
        *,
        file_path: str | None = None,
        details: dict | None = None,
        **kwargs,
    ) -> None:
        merged = details or {}
        if file_path:
            merged["file_path"] = file_path
        merged.update(kwargs)
        super().__init__(message, code="CONFIG_ERROR", details=merged)
        self.file_path = file_path


class ValidationError(PersonaAgentError):
    """Configuration or input validation failed."""

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        details: dict | None = None,
        **kwargs,
    ) -> None:
        merged = details or {}
        if field:
            merged["field"] = field
        merged.update(kwargs)
        super().__init__(message, code="VALIDATION_ERROR", details=merged)
        self.field = field


class FileNotFoundError(PersonaAgentError):
    """Required configuration file not found."""

    def __init__(self, file_path: str, *, details: dict | None = None) -> None:
        merged = details or {}
        merged["file_path"] = file_path
        super().__init__(
            f"Configuration file not found: {file_path}",
            code="FILE_NOT_FOUND",
            details=merged,
        )
        self.file_path = file_path


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

class LLMError(PersonaAgentError):
    """Error communicating with LLM API."""

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        details: dict | None = None,
        **kwargs,
    ) -> None:
        merged = details or {}
        if provider:
            merged["provider"] = provider
        merged.update(kwargs)
        super().__init__(message, code="LLM_ERROR", details=merged)
        self.provider = provider


class APIRateLimitError(LLMError):
    """API rate limit exceeded."""

    def __init__(
        self,
        provider: str,
        *,
        retry_after: int | None = None,
        details: dict | None = None,
    ) -> None:
        message = f"Rate limit exceeded for {provider}"
        if retry_after:
            message += f". Retry after {retry_after} seconds."
        merged = details or {}
        merged["provider"] = provider
        merged["retry_after"] = retry_after
        super().__init__(message, details=merged)
        self.code = "RATE_LIMIT_ERROR"
        self.retry_after = retry_after


class AuthenticationError(LLMError):
    """API authentication failed."""

    def __init__(self, provider: str, *, details: dict | None = None) -> None:
        merged = details or {}
        merged["provider"] = provider
        super().__init__(
            f"Authentication failed for {provider}",
            details=merged,
        )
        self.code = "AUTH_ERROR"
        self.provider = provider


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

class SecurityError(PersonaAgentError):
    """Security-related error (authentication, authorization, input sanitisation)."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "SECURITY_ERROR",
        details: dict | None = None,
        recoverable: bool = False,
    ) -> None:
        super().__init__(message, code=code, details=details, recoverable=recoverable)


# ---------------------------------------------------------------------------
# Mood
# ---------------------------------------------------------------------------

class MoodEngineError(PersonaAgentError):
    """Error in mood engine operations."""

    def __init__(
        self,
        message: str,
        *,
        mood_name: str | None = None,
        details: dict | None = None,
    ) -> None:
        merged = details or {}
        if mood_name:
            merged["mood_name"] = mood_name
        super().__init__(message, code="MOOD_ERROR", details=merged)
        self.mood_name = mood_name


class InvalidMoodError(PersonaAgentError):
    """Invalid mood state specified."""

    def __init__(
        self,
        mood_name: str,
        *,
        valid_moods: list[str] | None = None,
        details: dict | None = None,
    ) -> None:
        message = f"Invalid mood: {mood_name}"
        if valid_moods:
            message += f". Valid moods: {', '.join(valid_moods)}"
        merged = details or {}
        merged["mood_name"] = mood_name
        if valid_moods:
            merged["valid_moods"] = valid_moods
        super().__init__(message, code="INVALID_MOOD", details=merged)
        self.mood_name = mood_name
        self.valid_moods = valid_moods


__all__ = [
    # Base
    "PersonaAgentError",
    # Planning
    "PlanningError",
    "PlanCreationError",
    "PlanExecutionError",
    "TaskExecutionError",
    "DependencyError",
    "CyclicDependencyError",
    "PlanNotFoundError",
    "InvalidPlanStateError",
    "PlanningConfigError",
    # Memory
    "MemoryError",
    "CompactionError",
    "SummarizationError",
    "MemoryGroupError",
    "SchedulerError",
    "MemoryConfigurationError",
    "MemoryStoreError",
    "UserNotFoundError",
    "ConversationNotFoundError",
    # Tools / Skills
    "ToolError",
    "SkillError",
    "SkillNotFoundError",
    "SkillExecutionError",
    # Evolution
    "EvolutionError",
    "TrackingError",
    "GenerationError",
    "ProposalError",
    "InvalidEvolutionModeError",
    "EvolutionValidationError",
    # Config
    "ConfigError",
    "ValidationError",
    "FileNotFoundError",
    # LLM
    "LLMError",
    "APIRateLimitError",
    "AuthenticationError",
    # Security
    "SecurityError",
    # Mood
    "MoodEngineError",
    "InvalidMoodError",
]
