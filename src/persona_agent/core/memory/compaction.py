"""Memory compaction system for summarizing old memories.

Provides MemoryCompactor to compress old episodic memories into summaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from persona_agent.core.hierarchical_memory import EpisodicMemory


@dataclass
class CompactionResult:
    """Result of memory compaction operation."""

    original_count: int
    compacted_count: int
    summaries_created: int
    bytes_saved: int


class MemorySummarizer:
    """Summarizes groups of memories into concise summaries."""

    def __init__(self, llm_client: Any | None = None) -> None:
        """Initialize summarizer.

        Args:
            llm_client: Optional LLM client for generating summaries
        """
        self.llm_client = llm_client

    async def summarize_memories(
        self,
        memories: list[dict[str, Any]],
        max_length: int = 500,
    ) -> str:
        """Summarize a group of memories.

        Args:
            memories: List of memory entries with content
            max_length: Maximum length of summary

        Returns:
            Generated summary string
        """
        if not memories:
            return ""

        if self.llm_client is None:
            # Fallback: simple concatenation
            contents = [m.get("content", "")[:200] for m in memories]
            summary = " | ".join(contents)
            return summary[:max_length]

        # Use LLM to generate summary
        memory_texts = []
        for i, mem in enumerate(memories, 1):
            content = mem.get("content", "")
            memory_texts.append(f"{i}. {content}")

        prompt = f"""Summarize the following conversation memories into a concise summary.

Memories:
{"\n".join(memory_texts)}

Provide a brief summary (max {max_length} chars) capturing the key points and themes."""

        response = await self.llm_client.chat([{"role": "user", "content": prompt}])
        return response.content[:max_length]


class MemoryCompactor:
    """Compact old episodic memories into summaries."""

    def __init__(
        self,
        episodic_memory: EpisodicMemory,
        summarizer: MemorySummarizer | None = None,
    ) -> None:
        """Initialize compactor.

        Args:
            episodic_memory: EpisodicMemory instance to compact
            summarizer: Optional custom summarizer
        """
        self.episodic = episodic_memory
        self.summarizer = summarizer or MemorySummarizer()
        self._compacting = False

    def is_compacting(self) -> bool:
        """Check if compaction is currently in progress.

        Returns:
            True if compaction is running
        """
        return self._compacting

    async def compact_memories(
        self,
        older_than_days: int = 7,
        min_memories_per_group: int = 5,
        max_summary_length: int = 500,
    ) -> CompactionResult:
        """Compact old memories into summaries.

        Args:
            older_than_days: Only compact memories older than this many days
            min_memories_per_group: Minimum memories needed to create a summary
            max_summary_length: Maximum length of generated summaries

        Returns:
            CompactionResult with statistics
        """
        cutoff = datetime.now() - timedelta(days=older_than_days)

        # Get old memories from episodic storage
        old_memories = self._get_memories_older_than(cutoff)

        if len(old_memories) < min_memories_per_group:
            return CompactionResult(
                original_count=len(old_memories),
                compacted_count=0,
                summaries_created=0,
                bytes_saved=0,
            )

        # Group by time window (daily)
        groups = self._group_by_time_window(old_memories, window_days=1)

        summaries_created = 0
        total_bytes_saved = 0
        compacted_count = 0

        for _window, memories in groups.items():
            if len(memories) < min_memories_per_group:
                continue

            # Generate summary
            summary = await self.summarizer.summarize_memories(
                memories,
                max_length=max_summary_length,
            )

            # Mark memories as compacted
            for mem in memories:
                mem["metadata"] = mem.get("metadata", {})
                mem["metadata"]["compacted"] = True
                mem["metadata"]["summary"] = summary
                total_bytes_saved += len(mem.get("content", ""))
                compacted_count += 1

            summaries_created += 1

        return CompactionResult(
            original_count=len(old_memories),
            compacted_count=compacted_count,
            summaries_created=summaries_created,
            bytes_saved=total_bytes_saved,
        )

    def _get_memories_older_than(self, cutoff: datetime) -> list[dict[str, Any]]:
        """Get memories older than cutoff date.

        Args:
            cutoff: Datetime cutoff

        Returns:
            List of memory dictionaries
        """
        old_memories = []
        # Access internal episodes dict if available
        if hasattr(self.episodic, "_episodes"):
            episodes = self.episodic._episodes
            if isinstance(episodes, dict):
                for entry in episodes.values():
                    mem_dict = self._entry_to_dict(entry)
                    timestamp = mem_dict.get("timestamp")
                    if timestamp:
                        if isinstance(timestamp, (int, float)):
                            entry_time = datetime.fromtimestamp(timestamp)
                        elif isinstance(timestamp, datetime):
                            entry_time = timestamp.replace(tzinfo=None)
                        else:
                            continue
                        if entry_time < cutoff and not mem_dict.get("metadata", {}).get("compacted"):
                            old_memories.append(mem_dict)
            else:
                # Handle list case
                for entry in episodes:
                    mem_dict = self._entry_to_dict(entry)
                    timestamp = mem_dict.get("timestamp")
                    if timestamp:
                        if isinstance(timestamp, (int, float)):
                            entry_time = datetime.fromtimestamp(timestamp)
                        elif isinstance(timestamp, datetime):
                            entry_time = timestamp.replace(tzinfo=None)
                        else:
                            continue
                        if entry_time < cutoff and not mem_dict.get("metadata", {}).get("compacted"):
                            old_memories.append(mem_dict)

        return sorted(old_memories, key=lambda m: m.get("timestamp", 0))

    def _entry_to_dict(self, entry: Any) -> dict[str, Any]:
        """Convert episodic entry to dictionary.

        Args:
            entry: EpisodicEntry or dict

        Returns:
            Dictionary representation
        """
        if isinstance(entry, dict):
            return entry

        # Convert object attributes to dict
        return {
            "content": getattr(entry, "content", ""),
            "timestamp": getattr(entry, "timestamp", None),
            "metadata": getattr(entry, "metadata", {}),
            "entities": getattr(entry, "entities", []),
        }

    def _group_by_time_window(
        self,
        memories: list[dict[str, Any]],
        window_days: int,
    ) -> dict[datetime, list[dict[str, Any]]]:
        """Group memories by time window.

        Args:
            memories: List of memory dictionaries
            window_days: Size of time window in days

        Returns:
            Dict mapping window start to list of memories
        """
        from collections import defaultdict

        groups: dict[datetime, list[dict[str, Any]]] = defaultdict(list)

        for mem in memories:
            timestamp = mem.get("timestamp")
            if timestamp:
                if isinstance(timestamp, (int, float)):
                    mem_time = datetime.fromtimestamp(timestamp)
                else:
                    mem_time = timestamp

                # Round to start of window
                days_since_epoch = mem_time.toordinal()
                window_start = datetime.fromordinal(
                    (days_since_epoch // window_days) * window_days
                )
                groups[window_start].append(mem)

        return dict(groups)
