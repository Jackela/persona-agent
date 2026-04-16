"""Unit tests for memory compaction."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from persona_agent.core.memory.compaction import (
    CompactionConfig,
    CompactionResult,
    CompactionStatistics,
    MemoryCompactor,
)
from persona_agent.core.memory.exceptions import CompactionError


class TestCompactionResult:
    """Tests for CompactionResult."""

    def test_creation(self):
        """Test basic result creation."""
        result = CompactionResult(
            original_count=100,
            compacted_count=90,
            summaries_created=5,
            bytes_saved=10000,
            duration_ms=1000,
        )

        assert result.original_count == 100
        assert result.compacted_count == 90
        assert result.summaries_created == 5
        assert result.bytes_saved == 10000

    def test_compaction_ratio(self):
        """Test compaction ratio calculation."""
        result = CompactionResult(
            original_count=100,
            compacted_count=75,
            summaries_created=3,
            bytes_saved=5000,
        )

        assert result.compaction_ratio == 0.75

    def test_compaction_ratio_zero(self):
        """Test ratio when original count is zero."""
        result = CompactionResult(
            original_count=0,
            compacted_count=0,
            summaries_created=0,
            bytes_saved=0,
        )

        assert result.compaction_ratio == 0.0

    def test_is_successful(self):
        """Test success status."""
        success = CompactionResult(
            original_count=10,
            compacted_count=10,
            summaries_created=1,
            bytes_saved=100,
        )
        assert success.is_successful

        failure = CompactionResult(
            original_count=10,
            compacted_count=0,
            summaries_created=0,
            bytes_saved=0,
            errors=["Some error"],
        )
        assert not failure.is_successful

    def test_to_dict(self):
        """Test dictionary serialization."""
        result = CompactionResult(
            original_count=100,
            compacted_count=90,
            summaries_created=5,
            bytes_saved=10000,
        )

        data = result.to_dict()

        assert data["original_count"] == 100
        assert data["compacted_count"] == 90
        assert data["compaction_ratio"] == 0.9
        assert data["is_successful"] is True


class TestCompactionConfig:
    """Tests for CompactionConfig."""

    def test_defaults(self):
        """Test default configuration."""
        config = CompactionConfig()

        assert config.enabled is True
        assert config.older_than_days == 7
        assert config.min_group_size == 5
        assert config.max_summary_length == 500
        assert config.preserve_recent == 1
        assert "summary" in config.excluded_types

    def test_validation_older_than_days(self):
        """Test validation of older_than_days."""
        with pytest.raises(ValueError, match="older_than_days"):
            CompactionConfig(older_than_days=0)

    def test_validation_min_group_size(self):
        """Test validation of min_group_size."""
        with pytest.raises(ValueError, match="min_group_size"):
            CompactionConfig(min_group_size=1)

    def test_validation_max_summary_length(self):
        """Test validation of max_summary_length."""
        with pytest.raises(ValueError, match="max_summary_length"):
            CompactionConfig(max_summary_length=50)


class TestCompactionStatistics:
    """Tests for CompactionStatistics."""

    def test_record_compaction(self):
        """Test recording compaction results."""
        stats = CompactionStatistics()

        result = CompactionResult(
            original_count=100,
            compacted_count=90,
            summaries_created=5,
            bytes_saved=10000,
        )

        stats.record_compaction(result)

        assert stats.total_compactions == 1
        assert stats.total_memories_compacted == 90
        assert stats.total_summaries_created == 5
        assert stats.total_bytes_saved == 10000
        assert stats.last_compaction_result == result
        assert stats.last_compaction_time is not None

    def test_record_compaction_with_errors(self):
        """Test recording compaction with errors."""
        stats = CompactionStatistics()

        result = CompactionResult(
            original_count=100,
            compacted_count=0,
            summaries_created=0,
            bytes_saved=0,
            errors=["Error 1", "Error 2"],
        )

        stats.record_compaction(result)

        assert stats.errors_count == 2

    def test_to_dict(self):
        """Test statistics serialization."""
        stats = CompactionStatistics()
        stats.total_compactions = 5
        stats.total_memories_compacted = 500

        data = stats.to_dict()

        assert data["total_compactions"] == 5
        assert data["total_memories_compacted"] == 500


class TestMemoryCompactor:
    """Tests for MemoryCompactor."""

    @pytest.fixture
    def mock_episodic_memory(self):
        """Create a mock episodic memory."""
        memory = MagicMock()
        memory._episodes = {}
        return memory

    @pytest.fixture
    def mock_summarizer(self):
        """Create a mock summarizer."""
        summarizer = AsyncMock()
        from persona_agent.core.memory.summarizer import SummaryMetadata

        summarizer.summarize.return_value = (
            "Test summary",
            SummaryMetadata(original_count=3, confidence=0.9),
        )
        return summarizer

    def test_init(self, mock_episodic_memory, mock_summarizer):
        """Test compactor initialization."""
        compactor = MemoryCompactor(mock_episodic_memory, mock_summarizer)

        assert compactor.episodic_memory == mock_episodic_memory
        assert compactor.summarizer == mock_summarizer
        assert compactor.config.enabled is True

    @pytest.mark.asyncio
    async def test_compact_memories_disabled(self, mock_episodic_memory):
        """Test compaction when disabled."""
        config = CompactionConfig(enabled=False)
        compactor = MemoryCompactor(mock_episodic_memory, config=config)

        result = await compactor.compact_memories()

        assert result.original_count == 0
        assert result.compacted_count == 0

    @pytest.mark.asyncio
    async def test_compact_memories_concurrent_prevention(
        self, mock_episodic_memory, mock_summarizer
    ):
        """Test that concurrent compaction is prevented."""
        compactor = MemoryCompactor(mock_episodic_memory, mock_summarizer)
        compactor._is_compacting = True

        result = await compactor.compact_memories()

        assert result.errors == ["Compaction already in progress"]

    def test_get_compaction_candidates(self, mock_episodic_memory):
        """Test identifying compaction candidates."""
        from persona_agent.core.hierarchical_memory import EpisodicEntry

        # Create test memories
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(days=10)

        mock_episodic_memory._episodes = {
            "old1": EpisodicEntry(
                id="old1",
                content="Old memory 1",
                timestamp=old_time,
                importance=0.5,
                metadata={},
            ),
            "old2": EpisodicEntry(
                id="old2",
                content="Old memory 2",
                timestamp=old_time,
                importance=0.5,
                metadata={},
            ),
            "recent": EpisodicEntry(
                id="recent",
                content="Recent memory",
                timestamp=now,
                importance=0.5,
                metadata={},
            ),
            "compacted": EpisodicEntry(
                id="compacted",
                content="Already compacted",
                timestamp=old_time,
                importance=0.5,
                metadata={"compacted": True},
            ),
        }

        compactor = MemoryCompactor(mock_episodic_memory)
        candidates = compactor._get_compaction_candidates(older_than_days=7)

        assert len(candidates) == 2
        assert all(c.id in ["old1", "old2"] for c in candidates)

    def test_group_by_time_window(self, mock_episodic_memory):
        """Test memory grouping by time window."""
        from persona_agent.core.hierarchical_memory import EpisodicEntry

        window1 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        window2 = datetime(2024, 1, 8, tzinfo=timezone.utc)

        memories = [
            EpisodicEntry(
                id="m1",
                content="Memory 1",
                timestamp=window1,
                importance=0.5,
            ),
            EpisodicEntry(
                id="m2",
                content="Memory 2",
                timestamp=window1,
                importance=0.5,
            ),
            EpisodicEntry(
                id="m3",
                content="Memory 3",
                timestamp=window2,
                importance=0.5,
            ),
        ]

        compactor = MemoryCompactor(mock_episodic_memory)
        groups = compactor._group_by_time_window(memories, window_days=7)

        # Should have 2 groups (one for each week)
        assert len(groups) == 2

    @pytest.mark.asyncio
    async def test_compact_group(self, mock_episodic_memory, mock_summarizer):
        """Test compacting a memory group."""
        from persona_agent.core.hierarchical_memory import EpisodicEntry

        now = datetime.now(timezone.utc)

        memories = [
            EpisodicEntry(
                id="m1",
                content="Memory 1 content",
                timestamp=now,
                importance=0.5,
                entities=["entity1"],
            ),
            EpisodicEntry(
                id="m2",
                content="Memory 2 content",
                timestamp=now,
                importance=0.5,
                entities=["entity2"],
            ),
        ]

        # Mock store_episode to return a summary entry
        mock_summary = MagicMock()
        mock_summary.id = "summary_123"
        mock_episodic_memory.store_episode = AsyncMock(return_value=mock_summary)

        compactor = MemoryCompactor(mock_episodic_memory, mock_summarizer)
        result = await compactor._compact_group(memories, "2024-01-15")

        assert result == mock_summary
        assert mock_episodic_memory.store_episode.called

        # Check that memories were marked as compacted
        assert memories[0].metadata["compacted"] is True
        assert memories[0].metadata["summary_id"] == "summary_123"

    def test_get_statistics(self, mock_episodic_memory):
        """Test getting statistics."""
        compactor = MemoryCompactor(mock_episodic_memory)
        stats = compactor.get_statistics()

        assert isinstance(stats, CompactionStatistics)
        assert stats.total_compactions == 0

    def test_is_compacting(self, mock_episodic_memory):
        """Test compaction status check."""
        compactor = MemoryCompactor(mock_episodic_memory)

        assert not compactor.is_compacting()

        compactor._is_compacting = True
        assert compactor.is_compacting()
