"""Memory compaction and management system.

This module provides automatic memory compaction to prevent unbounded growth
by summarizing old episodic memories into higher-level summaries.
"""

from persona_agent.core.memory.compaction import (
    CompactionConfig,
    CompactionResult,
    CompactionStatistics,
    MemoryCompactor,
)
from persona_agent.core.memory.exceptions import (
    CompactionError,
    MemoryGroupError,
    SummarizationError,
)
from persona_agent.core.memory.scheduler import AutoCompactionScheduler
from persona_agent.core.memory.summarizer import MemorySummarizer

__version__ = "1.0.0"

__all__ = [
    # Compaction
    "MemoryCompactor",
    "CompactionResult",
    "CompactionConfig",
    "CompactionStatistics",
    # Summarizer
    "MemorySummarizer",
    # Scheduler
    "AutoCompactionScheduler",
    # Exceptions
    "CompactionError",
    "SummarizationError",
    "MemoryGroupError",
]
