"""Custom exceptions for Persona Agent.

This module re-exports all exceptions from the unified hierarchy.
All classes are kept for backward compatibility.
"""

from __future__ import annotations

from persona_agent.exceptions import (
    AgentFileNotFoundError,
    AgentMemoryError,
    APIRateLimitError,
    AuthenticationError,
    ConfigError,
    ConversationNotFoundError,
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

ConfigurationError = ConfigError
FileNotFoundError = AgentFileNotFoundError
MemoryError = AgentMemoryError

__all__ = [
    "PersonaAgentError",
    "ConfigurationError",
    "ValidationError",
    "AgentFileNotFoundError",
    "AgentMemoryError",
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
