"""Exceptions for the memory compaction system."""

from __future__ import annotations


class MemoryError(Exception):
    """Base exception for memory-related errors."""

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class CompactionError(MemoryError):
    """Raised when memory compaction fails.

    This can occur due to:
    - LLM summarization failures
    - Storage errors during compaction
    - Invalid configuration
    """

    pass


class SummarizationError(CompactionError):
    """Raised when LLM summarization fails.

    This typically indicates:
    - LLM service unavailable
    - Invalid memory content
    - Response parsing errors
    """

    def __init__(
        self,
        message: str,
        *,
        memory_count: int | None = None,
        prompt_length: int | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(message, details=details)
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
        self.group_date = group_date
        self.memory_count = memory_count


class SchedulerError(MemoryError):
    """Raised when compaction scheduling fails."""

    pass


class ConfigurationError(MemoryError):
    """Raised when memory configuration is invalid."""

    pass


__all__ = [
    "MemoryError",
    "CompactionError",
    "SummarizationError",
    "MemoryGroupError",
    "SchedulerError",
    "ConfigurationError",
]
