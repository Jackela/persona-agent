"""Custom exceptions for Persona Agent."""


class PersonaAgentError(Exception):
    """Base exception for all Persona Agent errors.

    All custom exceptions should inherit from this class to allow
    callers to catch all application-specific errors in one block.
    """

    def __init__(self, message: str, code: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.code = code or "UNKNOWN_ERROR"
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"[{self.code}] {self.message} - Details: {self.details}"
        return f"[{self.code}] {self.message}"


class ConfigurationError(PersonaAgentError):
    """Error in configuration files or settings."""

    def __init__(self, message: str, file_path: str | None = None, **kwargs):
        super().__init__(
            message,
            code="CONFIG_ERROR",
            details={"file_path": file_path, **kwargs} if file_path else kwargs,
        )


class ValidationError(PersonaAgentError):
    """Configuration validation failed."""

    def __init__(self, message: str, field: str | None = None, **kwargs):
        details = kwargs.copy()
        if field:
            details["field"] = field
        super().__init__(
            message,
            code="VALIDATION_ERROR",
            details=details,
        )


class FileNotFoundError(PersonaAgentError):
    """Required configuration file not found."""

    def __init__(self, file_path: str, **kwargs):
        super().__init__(
            f"Configuration file not found: {file_path}",
            code="FILE_NOT_FOUND",
            details={"file_path": file_path, **kwargs},
        )


class MemoryStoreError(PersonaAgentError):
    """Error in memory store operations."""

    def __init__(self, message: str, operation: str | None = None, **kwargs):
        super().__init__(
            message,
            code="MEMORY_ERROR",
            details={"operation": operation, **kwargs} if operation else kwargs,
        )


class UserNotFoundError(PersonaAgentError):
    """Requested user not found in memory store."""

    def __init__(self, user_id: str, **kwargs):
        super().__init__(
            f"User not found: {user_id}",
            code="USER_NOT_FOUND",
            details={"operation": "get_user", "user_id": user_id, **kwargs},
        )


class ConversationNotFoundError(PersonaAgentError):
    """Requested conversation not found."""

    def __init__(self, conversation_id: str, **kwargs):
        super().__init__(
            f"Conversation not found: {conversation_id}",
            code="CONVERSATION_NOT_FOUND",
            details={"operation": "get_conversation", "conversation_id": conversation_id, **kwargs},
        )


class LLMError(PersonaAgentError):
    """Error communicating with LLM API."""

    def __init__(self, message: str, provider: str | None = None, **kwargs):
        super().__init__(
            message,
            code="LLM_ERROR",
            details={"provider": provider, **kwargs} if provider else kwargs,
        )


class APIRateLimitError(PersonaAgentError):
    """API rate limit exceeded."""

    def __init__(self, provider: str, retry_after: int | None = None, **kwargs):
        message = f"Rate limit exceeded for {provider}"
        if retry_after:
            message += f". Retry after {retry_after} seconds."

        super().__init__(
            message,
            code="RATE_LIMIT_ERROR",
            details={"provider": provider, "retry_after": retry_after, **kwargs},
        )


class AuthenticationError(PersonaAgentError):
    """API authentication failed."""

    def __init__(self, provider: str, **kwargs):
        super().__init__(
            f"Authentication failed for {provider}",
            code="AUTH_ERROR",
            details={"provider": provider, **kwargs},
        )


class SkillError(PersonaAgentError):
    """Error in skill system."""

    def __init__(self, message: str, skill_name: str | None = None, **kwargs):
        super().__init__(
            message,
            code="SKILL_ERROR",
            details={"skill_name": skill_name, **kwargs} if skill_name else kwargs,
        )


class SkillNotFoundError(PersonaAgentError):
    """Requested skill not found in registry."""

    def __init__(self, skill_name: str, **kwargs):
        super().__init__(
            f"Skill not found: {skill_name}",
            code="SKILL_NOT_FOUND",
            details={"skill_name": skill_name, **kwargs},
        )


class SkillExecutionError(PersonaAgentError):
    """Error executing a skill."""

    def __init__(self, skill_name: str, original_error: Exception, **kwargs):
        super().__init__(
            f"Error executing skill '{skill_name}': {original_error}",
            code="SKILL_EXECUTION_ERROR",
            details={
                "skill_name": skill_name,
                "original_error_type": type(original_error).__name__,
                **kwargs,
            },
        )


class MoodEngineError(PersonaAgentError):
    """Error in mood engine operations."""

    def __init__(self, message: str, mood_name: str | None = None, **kwargs):
        super().__init__(
            message,
            code="MOOD_ERROR",
            details={"mood_name": mood_name, **kwargs} if mood_name else kwargs,
        )


class InvalidMoodError(PersonaAgentError):
    """Invalid mood state specified."""

    def __init__(self, mood_name: str, valid_moods: list[str] | None = None, **kwargs):
        message = f"Invalid mood: {mood_name}"
        if valid_moods:
            message += f". Valid moods: {', '.join(valid_moods)}"

        super().__init__(
            message,
            code="INVALID_MOOD",
            details={"mood_name": mood_name, "valid_moods": valid_moods, **kwargs},
        )
