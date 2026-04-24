"""Custom exceptions for Persona Agent.

This module re-exports all exceptions from the unified hierarchy.
All classes are kept for backward compatibility.
"""

from __future__ import annotations

from persona_agent.exceptions import (
    APIRateLimitError,
    AuthenticationError,
    ConversationNotFoundError,
    FileNotFoundError,
    InvalidMoodError,
    LLMError,
    MemoryStoreError,
    MoodEngineError,
    PersonaAgentError,
    SecurityError,
    SkillError,
    SkillExecutionError,
    SkillNotFoundError,
    UserNotFoundError,
    ValidationError,
)
from persona_agent.exceptions import (
    ConfigError as ConfigurationError,
)

__all__ = [
    "PersonaAgentError",
    "ConfigurationError",
    "ValidationError",
    "FileNotFoundError",
    "MemoryStoreError",
    "UserNotFoundError",
    "ConversationNotFoundError",
    "LLMError",
    "APIRateLimitError",
    "AuthenticationError",
    "SkillError",
    "SkillNotFoundError",
    "SkillExecutionError",
    "MoodEngineError",
    "InvalidMoodError",
    "SecurityError",
]
