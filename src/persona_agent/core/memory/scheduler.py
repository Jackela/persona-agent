"""Memory compaction scheduler for automatic compaction runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from persona_agent.core.memory.compaction import CompactionResult, MemoryCompactor


@dataclass
class SchedulerConfig:
    """Configuration for auto-compaction scheduler.

    Attributes:
        check_interval_hours: How often to check if compaction is needed
        memory_threshold: Minimum number of memories before triggering compaction
    """

    check_interval_hours: int = 24
    memory_threshold: int = 1000


class AutoCompactionScheduler:
    """Schedule automatic memory compaction runs."""

    def __init__(
        self,
        compactor: MemoryCompactor,
        config: SchedulerConfig | None = None,
    ) -> None:
        """Initialize scheduler.

        Args:
            compactor: MemoryCompactor instance to use
            config: SchedulerConfig with timing and threshold settings
        """
        self.compactor = compactor
        self.config = config or SchedulerConfig()
        self._last_check: datetime | None = None

    def _should_check(self) -> bool:
        """Check if enough time has passed since last check.

        Returns:
            True if compaction check should run
        """
        if self._last_check is None:
            return True

        now = datetime.now(UTC)
        hours_since_last = (now - self._last_check).total_seconds() / 3600
        return hours_since_last >= self.config.check_interval_hours

    async def trigger_compaction(self) -> CompactionResult | None:
        """Manually trigger compaction check and run if conditions met.

        Returns:
            CompactionResult if compaction ran, None if skipped
        """
        self._last_check = datetime.now(UTC)

        # Check memory count threshold
        memory_count = self._get_memory_count()
        if memory_count < self.config.memory_threshold:
            return None

        # Run compaction
        return await self.compactor.compact_memories()

    async def maybe_compact(self) -> CompactionResult | None:
        """Check if compaction is needed and run if so.

        Returns:
            CompactionResult if compaction ran, None if skipped
        """
        if not self._should_check():
            return None

        return await self.trigger_compaction()

    def _get_memory_count(self) -> int:
        """Get current memory count from episodic storage.

        Returns:
            Number of memories in episodic storage
        """
        # Try 'episodic' first (real compactor), then 'episodic_memory' (mock in tests)
        episodic = getattr(self.compactor, "episodic", None) or getattr(self.compactor, "episodic_memory", None)
        if episodic is None:
            return 0
        if hasattr(episodic, "_episodes"):
            episodes = episodic._episodes
            if isinstance(episodes, dict):
                return len(episodes)
            return len(episodes)
        return 0

    def is_compacting(self) -> bool:
        """Check if compaction is currently running.

        Returns:
            False (compaction is synchronous for now)
        """
        return False
