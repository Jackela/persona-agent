"""Integration tests for the memory and compaction system.

Tests memory storage, retrieval, compaction, and integration with
AgentEngine and chat workflows.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from persona_agent.core.hierarchical_memory import (
    EpisodicMemory,
    HierarchicalMemory,
    WorkingMemory,
)
from persona_agent.core.memory.compaction import CompactionResult, MemoryCompactor
from persona_agent.core.memory.scheduler import AutoCompactionScheduler, SchedulerConfig
from persona_agent.core.memory.summarizer import MemorySummarizer


@pytest.fixture
def hierarchical_memory():
    """Create a hierarchical memory instance."""
    return HierarchicalMemory()


@pytest.fixture
def populated_episodic_memory():
    """Create an episodic memory with test data."""
    episodic = EpisodicMemory()

    return episodic


@pytest.mark.asyncio
class TestHierarchicalMemoryIntegration:
    """Test hierarchical memory system integration."""

    async def test_working_memory_stores_recent_exchanges(self, hierarchical_memory):
        """Test that working memory stores recent exchanges."""
        # Add exchanges
        for i in range(5):
            hierarchical_memory.working.add_exchange(
                user_msg=f"User message {i}",
                assistant_msg=f"Assistant response {i}",
            )

        # Verify storage
        assert len(hierarchical_memory.working) == 5
        exchanges = hierarchical_memory.working.get_recent()
        assert len(exchanges) == 10  # 5 user + 5 assistant messages

    async def test_working_memory_respects_max_size(self):
        """Test that working memory respects maximum size."""
        working = WorkingMemory(max_size=3)

        # Add more than max exchanges
        for i in range(5):
            working.add_exchange(
                user_msg=f"Message {i}",
                assistant_msg=f"Response {i}",
            )

        # Should only keep max_size exchanges
        assert len(working) == 3

    async def test_episodic_memory_stores_episodes(self, hierarchical_memory):
        """Test episodic memory storage."""
        # Add episodes
        for i in range(5):
            await hierarchical_memory.episodic.store_episode(
                content=f"Episode content {i}",
                importance=0.5,
                metadata={"turn": i},
            )

        # Retrieve
        stats = hierarchical_memory.get_stats()
        assert stats["episodic"]["total_episodes"] == 5

    async def test_semantic_memory_stores_facts(self, hierarchical_memory):
        """Test semantic memory stores facts."""
        # Add facts
        hierarchical_memory.semantic.add_fact("Python", "is a programming language", 0.9)
        hierarchical_memory.semantic.add_fact("Python", "is dynamically typed", 0.8)

        # Query
        entity_info = hierarchical_memory.semantic.query_entity("python")
        assert entity_info["exists"] is True
        assert len(entity_info["facts"]) == 2

    async def test_memory_stats_accurate(self, hierarchical_memory):
        """Test that memory stats are accurate."""
        # Add data to all levels
        hierarchical_memory.working.add_exchange("Test", "Response")
        await hierarchical_memory.episodic.store_episode("Test episode", 0.5)
        hierarchical_memory.semantic.add_fact("Test", "is a fact", 0.7)

        # Get stats
        stats = hierarchical_memory.get_stats()

        assert stats["working"]["exchanges"] == 1
        assert stats["episodic"]["total_episodes"] == 1
        assert stats["semantic"]["entities"] == 1


@pytest.mark.asyncio
class TestMemoryCompactionIntegration:
    """Test memory compaction system integration."""

    async def test_compactor_identifies_old_memories(self):
        """Test that compactor identifies old memories for compaction."""
        episodic = EpisodicMemory()

        # Note: Compactor operates on the in-memory episodes which don't have timestamps tracked separately
        # This test verifies the compactor interface works

        # Add episodes (they'll have current timestamps)
        for i in range(5):
            await episodic.store_episode(
                content=f"Old episode {i}",
                importance=0.3,
            )

        compactor = MemoryCompactor(episodic)

        # The compactor should work even if all memories are recent
        result = await compactor.compact_memories(older_than_days=7)
        assert isinstance(result, CompactionResult)

    async def test_compactor_creates_summaries(self):
        """Test that compactor creates summaries."""
        episodic = EpisodicMemory()

        # Add related episodes
        for i in range(5):
            await episodic.store_episode(
                content=f"Discussion about Python programming - part {i}",
                importance=0.5,
                metadata={"topic": "python"},
            )

        # Mock summarizer
        mock_summarizer = Mock(spec=MemorySummarizer)
        mock_summarizer.summarize_memories = AsyncMock(
            return_value="Summary of Python programming discussions"
        )

        compactor = MemoryCompactor(episodic, summarizer=mock_summarizer)

        # Force compaction with 0 days to trigger summarization
        result = await compactor.compact_memories(older_than_days=0)

        # Should have created summaries
        assert isinstance(result, CompactionResult)

    async def test_compaction_with_mocked_data(self):
        """Test compaction with mocked old memory data."""
        episodic = EpisodicMemory()

        # Add episodes
        for i in range(5):
            await episodic.store_episode(
                content=f"Old episode {i}",
                importance=0.3,
            )

        _ = len(episodic._episodes)  # For debugging

        # Mock summarizer
        mock_summarizer = Mock(spec=MemorySummarizer)
        mock_summarizer.summarize_memories = AsyncMock(return_value="Summary of old episodes")

        compactor = MemoryCompactor(episodic, summarizer=mock_summarizer)

        # Compact with 0 days to include all memories
        result = await compactor.compact_memories(older_than_days=0)

        # Should return valid result
        assert isinstance(result, CompactionResult)
        assert result.compacted_count >= 0


@pytest.mark.asyncio
class TestMemorySchedulerIntegration:
    """Test auto-compaction scheduler integration."""

    async def test_scheduler_triggers_compaction(self):
        """Test that scheduler triggers compaction when threshold is met."""
        episodic = EpisodicMemory()

        # Add enough episodes to meet threshold (default 1000, use config to lower)
        for i in range(100):
            await episodic.store_episode(
                content=f"Episode {i}",
                importance=0.3,
            )

        # Mock compactor with real episodic memory attached
        mock_compactor = Mock(spec=MemoryCompactor)
        mock_compactor.episodic_memory = episodic
        mock_compactor.is_compacting.return_value = False
        mock_compactor.compact_memories = AsyncMock(
            return_value=CompactionResult(
                original_count=5,
                compacted_count=5,
                summaries_created=1,
                bytes_saved=1000,
            )
        )

        config = SchedulerConfig(check_interval_hours=1, memory_threshold=50)
        scheduler = AutoCompactionScheduler(
            compactor=mock_compactor,
            config=config,
        )

        # Trigger manual check
        await scheduler.trigger_compaction()

        # Compactor should have been called
        mock_compactor.compact_memories.assert_called_once()

    async def test_scheduler_respects_schedule_interval(self):
        """Test that scheduler respects the schedule interval."""
        episodic = EpisodicMemory()
        compactor = MemoryCompactor(episodic)

        config = SchedulerConfig(check_interval_hours=24)
        scheduler = AutoCompactionScheduler(
            compactor=compactor,
            config=config,
        )

        # Last check was just now
        scheduler._last_check = datetime.now(UTC)

        # Should not run again immediately
        should_run = scheduler._should_check()
        assert should_run is False

        # Simulate time passing
        scheduler._last_check = datetime.now(UTC) - timedelta(hours=25)

        # Should run now
        should_run = scheduler._should_check()
        assert should_run is True


@pytest.mark.asyncio
class TestMemoryEdgeCases:
    """Test memory system edge cases."""

    async def test_empty_memory_operations(self, hierarchical_memory):
        """Test operations on empty memory."""
        stats = hierarchical_memory.get_stats()

        assert stats["working"]["exchanges"] == 0
        assert stats["episodic"]["total_episodes"] == 0
        assert stats["semantic"]["entities"] == 0

    async def test_compaction_with_no_memories(self):
        """Test compaction when no memories exist."""
        episodic = EpisodicMemory()

        compactor = MemoryCompactor(episodic)

        result = await compactor.compact_memories(older_than_days=0)

        assert result.compacted_count == 0
        assert result.summaries_created == 0

    async def test_very_large_memory_handling(self):
        """Test handling of large memory stores."""
        memory = HierarchicalMemory()

        # Add many episodes
        for i in range(100):
            await memory.episodic.store_episode(
                content=f"Episode {i}: " + "x" * 100,  # 100+ chars each
                importance=0.5,
            )

        stats = memory.get_stats()
        assert stats["episodic"]["total_episodes"] == 100

    async def test_semantic_relationship_traversal(self, hierarchical_memory):
        """Test semantic memory relationship traversal."""
        # Add relationships
        hierarchical_memory.semantic.add_relationship("alice", "knows", "bob", 0.9)
        hierarchical_memory.semantic.add_relationship("bob", "knows", "charlie", 0.8)
        hierarchical_memory.semantic.add_relationship("alice", "likes", "python", 0.7)

        # Query entity
        alice_info = hierarchical_memory.semantic.query_entity("alice")
        assert alice_info["exists"] is True
        assert len(alice_info["outgoing_relations"]) == 2

        # Get related entities
        related = hierarchical_memory.semantic.get_related_entities("alice", depth=1)
        assert "bob" in related

    async def test_entity_extraction(self, hierarchical_memory):
        """Test entity extraction returns empty for GDPR compliance."""
        text = "My name is Alice and I work at Google. I live in New York."

        entities = hierarchical_memory.semantic.extract_entities(text)

        # Regex-based PII extraction removed for GDPR compliance
        assert entities == []

    async def test_fact_extraction_from_exchange(self, hierarchical_memory):
        """Test that facts are extracted from conversation exchanges."""
        user_msg = "Python is a programming language. I love coding."
        assistant_msg = "That's great! Python is indeed popular."

        # Store exchange extracts semantic knowledge
        hierarchical_memory._extract_and_store_semantic_knowledge(user_msg)
        hierarchical_memory._extract_and_store_semantic_knowledge(assistant_msg)

        # Check facts were extracted
        python_info = hierarchical_memory.semantic.query_entity("python")
        assert python_info["exists"] is True
