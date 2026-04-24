"""Exceptions for the memory compaction system.

This module re-exports all memory exceptions from the unified hierarchy.
All classes are kept for backward compatibility.
"""

from __future__ import annotations

from persona_agent.exceptions import (
    AgentMemoryError,
    CompactionError,
    MemoryConfigurationError,
    MemoryGroupError,
    SchedulerError,
    SummarizationError,
)

__all__ = [
    "AgentMemoryError",
    "CompactionError",
    "SummarizationError",
    "MemoryGroupError",
    "SchedulerError",
    "MemoryConfigurationError",
]
