"""Automatic compaction scheduling.

This module provides background task scheduling for automatic
memory compaction at configurable intervals.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Callable

from persona_agent.core.memory.compaction import CompactionResult
from persona_agent.core.memory.exceptions import SchedulerError

if TYPE_CHECKING:
    from persona_agent.core.memory.compaction import MemoryCompactor

logger = logging.getLogger(__name__)


ProgressCallback = Callable[[str, Any], None]
"""Callback for compaction progress: (stage, data)"""


@dataclass
class SchedulerConfig:
    """Configuration for the compaction scheduler.

    Attributes:
        check_interval_hours: How often to check if compaction is needed
        memory_threshold: Minimum number of memories before compaction
        auto_start: Whether to start scheduler automatically
        max_concurrent: Maximum concurrent compaction operations
        retry_delay_minutes: Delay between retries on failure
    """

    check_interval_hours: float = 24.0
    memory_threshold: int = 1000
    auto_start: bool = False
    max_concurrent: int = 1
    retry_delay_minutes: float = 60.0

    def __post_init__(self):
        """Validate configuration."""
        if self.check_interval_hours < 0.5:
            raise ValueError("check_interval_hours must be at least 0.5")
        if self.memory_threshold < 10:
            raise ValueError("memory_threshold must be at least 10")


class AutoCompactionScheduler:
    """Schedule and manage automatic memory compaction.

    This class runs a background task that periodically checks
    if memory compaction is needed and triggers it automatically.

    Example:
        scheduler = AutoCompactionScheduler(compactor)
        await scheduler.start()
        # ... later ...
        await scheduler.stop()
    """

    def __init__(
        self,
        compactor: MemoryCompactor,
        config: SchedulerConfig | None = None,
    ) -> None:
        """Initialize the scheduler.

        Args:
            compactor: The memory compactor to use
            config: Scheduler configuration
        """
        self.compactor = compactor
        self.config = config or SchedulerConfig()

        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._is_running = False
        self._last_check: datetime | None = None
        self._last_result: CompactionResult | None = None
        self._progress_callback: ProgressCallback | None = None
        self._error_count = 0
        self._max_errors = 3

    async def start(self) -> None:
        """Start the background compaction scheduler.

        Raises:
            SchedulerError: If scheduler is already running
        """
        if self._is_running:
            raise SchedulerError("Scheduler is already running")

        if not self.compactor.config.enabled:
            logger.warning("Cannot start scheduler: compaction is disabled")
            return

        self._is_running = True
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_scheduler())

        logger.info(
            f"AutoCompactionScheduler started " f"(interval: {self.config.check_interval_hours}h)"
        )

    async def stop(self) -> None:
        """Stop the background compaction scheduler."""
        if not self._is_running:
            return

        self._is_running = False
        self._stop_event.set()

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        logger.info("AutoCompactionScheduler stopped")

    async def trigger_compaction(self) -> CompactionResult | None:
        """Manually trigger a compaction check.

        Returns:
            CompactionResult if compaction was performed, None otherwise
        """
        return await self._check_and_compact()

    def set_progress_callback(self, callback: ProgressCallback | None) -> None:
        """Set a callback for compaction progress updates."""
        self._progress_callback = callback

    def is_running(self) -> bool:
        """Check if the scheduler is running."""
        return self._is_running

    def get_status(self) -> dict[str, Any]:
        """Get current scheduler status."""
        return {
            "is_running": self._is_running,
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "last_result": self._last_result.to_dict() if self._last_result else None,
            "error_count": self._error_count,
            "config": {
                "check_interval_hours": self.config.check_interval_hours,
                "memory_threshold": self.config.memory_threshold,
            },
        }

    async def _run_scheduler(self) -> None:
        """Main scheduler loop."""
        while self._is_running:
            try:
                # Check if compaction is needed
                if self._should_check():
                    result = await self._check_and_compact()
                    if result and self._progress_callback:
                        self._progress_callback("completed", result.to_dict())

                # Reset error count on success
                self._error_count = 0

                # Wait for next check or stop signal
                wait_seconds = self.config.check_interval_hours * 3600
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=wait_seconds,
                    )
                except asyncio.TimeoutError:
                    pass  # Normal timeout, continue loop

            except asyncio.CancelledError:
                logger.debug("Scheduler task cancelled")
                break

            except Exception as e:
                self._error_count += 1
                logger.error(f"Scheduler error: {e}")

                if self._progress_callback:
                    self._progress_callback("error", {"message": str(e)})

                if self._error_count >= self._max_errors:
                    logger.error("Too many errors, stopping scheduler")
                    self._is_running = False
                    break

                # Wait before retry
                await asyncio.sleep(self.config.retry_delay_minutes * 60)

    def _should_check(self) -> bool:
        """Determine if we should check for compaction."""
        if self._last_check is None:
            return True

        elapsed = datetime.now(timezone.utc) - self._last_check
        check_interval = timedelta(hours=self.config.check_interval_hours)

        return elapsed >= check_interval

    async def _check_and_compact(self) -> CompactionResult | None:
        """Check if compaction is needed and perform it.

        Returns:
            CompactionResult if compaction was performed, None otherwise
        """
        self._last_check = datetime.now(timezone.utc)

        # Check if compactor is busy
        if self.compactor.is_compacting():
            logger.debug("Compactor is busy, skipping check")
            return None

        # Check memory count
        memory_count = len(self.compactor.episodic_memory._episodes)
        if memory_count < self.config.memory_threshold:
            logger.debug(
                f"Memory count ({memory_count}) below threshold "
                f"({self.config.memory_threshold})"
            )
            return None

        logger.info(
            f"Triggering compaction: {memory_count} memories "
            f"(threshold: {self.config.memory_threshold})"
        )

        if self._progress_callback:
            self._progress_callback(
                "starting",
                {"memory_count": memory_count},
            )

        try:
            result = await self.compactor.compact_memories()
            self._last_result = result

            logger.info(
                f"Compaction completed: {result.compacted_count} memories, "
                f"{result.summaries_created} summaries"
            )

            return result

        except Exception as e:
            logger.error(f"Compaction failed: {e}")
            raise


__all__ = [
    "AutoCompactionScheduler",
    "SchedulerConfig",
    "ProgressCallback",
]
