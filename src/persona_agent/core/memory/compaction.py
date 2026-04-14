"""Memory compaction implementation.

This module provides the core compaction logic for grouping and summarizing
old episodic memories to prevent unbounded growth.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from persona_agent.core.memory.exceptions import CompactionError, MemoryGroupError
from persona_agent.core.memory.summarizer import MemorySummarizer, SummaryMetadata

if TYPE_CHECKING:
    from persona_agent.core.memory.episodic_memory import EpisodicEntry, EpisodicMemory

logger = logging.getLogger(__name__)


@dataclass
class CompactionResult:
    """Result of a memory compaction operation.

    Attributes:
        original_count: Total number of memories considered
        compacted_count: Number of memories compacted (marked as compacted)
        summaries_created: Number of summary memories created
        bytes_saved: Estimated bytes saved
        duration_ms: Time taken for compaction in milliseconds
        errors: List of errors encountered during compaction
    """

    original_count: int
    compacted_count: int
    summaries_created: int
    bytes_saved: int
    duration_ms: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def compaction_ratio(self) -> float:
        """Calculate compaction ratio (0.0 to 1.0)."""
        if self.original_count == 0:
            return 0.0
        return self.compacted_count / self.original_count

    @property
    def is_successful(self) -> bool:
        """Check if compaction was successful (no errors)."""
        return len(self.errors) == 0

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "original_count": self.original_count,
            "compacted_count": self.compacted_count,
            "summaries_created": self.summaries_created,
            "bytes_saved": self.bytes_saved,
            "duration_ms": self.duration_ms,
            "compaction_ratio": self.compaction_ratio,
            "is_successful": self.is_successful,
            "errors": self.errors.copy(),
        }


@dataclass
class CompactionConfig:
    """Configuration for memory compaction.

    Attributes:
        enabled: Whether compaction is enabled
        older_than_days: Only compact memories older than this
        min_group_size: Minimum memories per group to compact
        max_summary_length: Maximum length of generated summaries
        preserve_recent: Number of recent days to always preserve
        excluded_types: Memory types to exclude from compaction
    """

    enabled: bool = True
    older_than_days: int = 7
    min_group_size: int = 5
    max_summary_length: int = 500
    preserve_recent: int = 1
    excluded_types: set[str] = field(default_factory=lambda: {"summary", "protected"})

    def __post_init__(self):
        """Validate configuration."""
        if self.older_than_days < 1:
            raise ValueError("older_than_days must be at least 1")
        if self.min_group_size < 2:
            raise ValueError("min_group_size must be at least 2")
        if self.max_summary_length < 100:
            raise ValueError("max_summary_length must be at least 100")


@dataclass
class CompactionStatistics:
    """Statistics about compaction operations.

    Tracks compaction history for monitoring and optimization.
    """

    total_compactions: int = 0
    total_memories_compacted: int = 0
    total_summaries_created: int = 0
    total_bytes_saved: int = 0
    last_compaction_time: datetime | None = None
    last_compaction_result: CompactionResult | None = None
    errors_count: int = 0

    def record_compaction(self, result: CompactionResult) -> None:
        """Record a compaction result."""
        self.total_compactions += 1
        self.total_memories_compacted += result.compacted_count
        self.total_summaries_created += result.summaries_created
        self.total_bytes_saved += result.bytes_saved
        self.last_compaction_time = datetime.now(timezone.utc)
        self.last_compaction_result = result
        if result.errors:
            self.errors_count += len(result.errors)

    def to_dict(self) -> dict[str, Any]:
        """Convert statistics to dictionary."""
        return {
            "total_compactions": self.total_compactions,
            "total_memories_compacted": self.total_memories_compacted,
            "total_summaries_created": self.total_summaries_created,
            "total_bytes_saved": self.total_bytes_saved,
            "last_compaction_time": (
                self.last_compaction_time.isoformat() if self.last_compaction_time else None
            ),
            "errors_count": self.errors_count,
        }


class MemoryCompactor:
    """Compact old episodic memories into summaries.

    This class provides the core compaction logic:
    1. Identify memories eligible for compaction
    2. Group memories by time window
    3. Generate summaries for each group
    4. Store summaries and mark originals as compacted

    Example:
        compactor = MemoryCompactor(episodic_memory, llm_client)
        result = await compactor.compact_memories()
        print(f"Compacted {result.compacted_count} memories")
    """

    def __init__(
        self,
        episodic_memory: EpisodicMemory,
        summarizer: MemorySummarizer | None = None,
        config: CompactionConfig | None = None,
    ) -> None:
        """Initialize the compactor.

        Args:
            episodic_memory: The episodic memory store to compact
            summarizer: Summarizer for generating summaries (creates default if None)
            config: Compaction configuration
        """
        self.episodic_memory = episodic_memory
        self.summarizer = summarizer
        self.config = config or CompactionConfig()
        self.statistics = CompactionStatistics()
        self._lock = asyncio.Lock()
        self._is_compacting = False

    async def compact_memories(
        self,
        older_than_days: int | None = None,
        min_group_size: int | None = None,
    ) -> CompactionResult:
        """Compact old memories into summaries.

        Args:
            older_than_days: Override config.older_than_days
            min_group_size: Override config.min_group_size

        Returns:
            CompactionResult with operation statistics

        Raises:
            CompactionError: If compaction fails
        """
        if not self.config.enabled:
            logger.debug("Compaction is disabled")
            return CompactionResult(
                original_count=0,
                compacted_count=0,
                summaries_created=0,
                bytes_saved=0,
            )

        # Prevent concurrent compaction
        if self._is_compacting:
            logger.warning("Compaction already in progress")
            return CompactionResult(
                original_count=0,
                compacted_count=0,
                summaries_created=0,
                bytes_saved=0,
                errors=["Compaction already in progress"],
            )

        async with self._lock:
            self._is_compacting = True
            start_time = time.monotonic()

            try:
                return await self._do_compaction(
                    older_than_days or self.config.older_than_days,
                    min_group_size or self.config.min_group_size,
                )
            finally:
                self._is_compacting = False
                duration_ms = int((time.monotonic() - start_time) * 1000)
                logger.info(f"Compaction completed in {duration_ms}ms")

    async def _do_compaction(
        self,
        older_than_days: int,
        min_group_size: int,
    ) -> CompactionResult:
        """Internal compaction implementation."""
        result = CompactionResult(
            original_count=0,
            compacted_count=0,
            summaries_created=0,
            bytes_saved=0,
        )

        try:
            # Get memories eligible for compaction
            candidates = self._get_compaction_candidates(older_than_days)
            result.original_count = len(candidates)

            if len(candidates) < min_group_size:
                logger.debug(f"Not enough candidates: {len(candidates)} < {min_group_size}")
                return result

            # Group by time window
            groups = self._group_by_time_window(candidates, window_days=1)

            # Process each group
            for date_key, memories in groups.items():
                if len(memories) < min_group_size:
                    continue

                try:
                    summary_entry = await self._compact_group(memories, date_key)
                    if summary_entry:
                        result.compacted_count += len(memories)
                        result.summaries_created += 1
                        # Estimate bytes saved
                        original_size = sum(len(m.content) for m in memories)
                        summary_size = len(summary_entry.content)
                        result.bytes_saved += max(0, original_size - summary_size)

                except Exception as e:
                    error_msg = f"Failed to compact group {date_key}: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)

        except Exception as e:
            error_msg = f"Compaction failed: {e}"
            logger.exception(error_msg)
            result.errors.append(error_msg)
            raise CompactionError(error_msg) from e

        finally:
            self.statistics.record_compaction(result)

        return result

    def _get_compaction_candidates(
        self,
        older_than_days: int,
    ) -> list[EpisodicEntry]:
        """Get memories eligible for compaction."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        preserve_date = datetime.now(timezone.utc) - timedelta(days=self.config.preserve_recent)

        candidates: list[EpisodicEntry] = []

        for entry in self.episodic_memory._episodes.values():
            # Skip if too recent
            if entry.timestamp > preserve_date:
                continue

            # Skip if already compacted or excluded type
            if entry.metadata.get("compacted"):
                continue
            if entry.metadata.get("memory_type") in self.config.excluded_types:
                continue

            # Skip if has protected flag
            if entry.metadata.get("protected"):
                continue

            candidates.append(entry)

        return sorted(candidates, key=lambda m: m.timestamp)

    def _group_by_time_window(
        self,
        memories: list[EpisodicEntry],
        window_days: int,
    ) -> dict[str, list[EpisodicEntry]]:
        """Group memories by time window.

        Args:
            memories: Memories to group
            window_days: Size of each time window in days

        Returns:
            Dictionary mapping date keys to memory lists
        """
        from collections import defaultdict

        groups: dict[str, list[EpisodicEntry]] = defaultdict(list)

        for memory in memories:
            # Create date key based on window
            days_since_epoch = memory.timestamp.toordinal()
            window_start_ordinal = (days_since_epoch // window_days) * window_days
            window_start = datetime.fromordinal(window_start_ordinal).replace(tzinfo=timezone.utc)
            date_key = window_start.strftime("%Y-%m-%d")
            groups[date_key].append(memory)

        return dict(groups)

    async def _compact_group(
        self,
        memories: list[EpisodicEntry],
        date_key: str,
    ) -> Any | None:
        """Compact a group of memories into a summary.

        Args:
            memories: Memories to compact
            date_key: Date identifier for the group

        Returns:
            New summary entry or None if compaction failed
        """
        if not self.summarizer:
            logger.warning("No summarizer available, skipping compaction")
            return None

        # Generate summary
        summary_text, metadata = await self.summarizer.summarize(memories)

        # Collect all entities from original memories
        all_entities: set[str] = set()
        for memory in memories:
            all_entities.update(memory.entities)

        # Create summary entry
        summary_entry = await self.episodic_memory.store_episode(
            content=f"[Summary {date_key}] {summary_text}",
            importance=0.8,  # Higher importance for summaries
            entities=list(all_entities),
            metadata={
                "type": "compaction_summary",
                "original_count": len(memories),
                "date_range": date_key,
                "compacted_at": datetime.now(timezone.utc).isoformat(),
                "key_entities": metadata.key_entities,
                "key_themes": metadata.key_themes,
                "confidence": metadata.confidence,
            },
        )

        # Mark original memories as compacted
        for memory in memories:
            memory.metadata["compacted"] = True
            memory.metadata["summary_id"] = summary_entry.id

        logger.debug(f"Compacted {len(memories)} memories into summary {summary_entry.id}")

        return summary_entry

    def get_statistics(self) -> CompactionStatistics:
        """Get compaction statistics."""
        return self.statistics

    def is_compacting(self) -> bool:
        """Check if compaction is currently running."""
        return self._is_compacting


__all__ = [
    "MemoryCompactor",
    "CompactionResult",
    "CompactionConfig",
    "CompactionStatistics",
]
