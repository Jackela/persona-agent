"""Episodic memory - event-based experiences with vector retrieval."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from persona_agent.core.schemas import MemoryEntry, MemoryType


@dataclass
class EpisodicEntry:
    """An episodic memory entry with metadata."""

    id: str
    content: str
    timestamp: datetime
    importance: float
    entities: list[str] = field(default_factory=list)
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    access_count: int = 0
    last_accessed: datetime | None = None


class VectorStoreProtocol(Protocol):
    """Protocol for vector store implementations."""

    async def store(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        embedding: list[float] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int: ...

    async def retrieve_relevant(
        self,
        query: str,
        query_embedding: list[float] | None = None,
        session_id: str | None = None,
        limit: int = 5,
    ) -> list: ...


class EpisodicMemory:
    """Episodic memory - event-based experiences with vector retrieval.

    Episodic memories store specific events and experiences with:
    - Vector embeddings for semantic similarity search
    - Time decay weighting (older memories become less relevant)
    - Importance scoring for prioritization
    - Composite scoring combining similarity, importance, and recency
    """

    # Decay half-life in days (memories lose half relevance after this period)
    DECAY_HALF_LIFE_DAYS: float = 7.0

    def __init__(self, vector_store: VectorStoreProtocol | None = None):
        """Initialize episodic memory.

        Args:
            vector_store: Optional vector store for persistence and search
        """
        self.vector_store = vector_store
        self._episodes: dict[str, EpisodicEntry] = {}

    async def store_episode(
        self,
        content: str,
        importance: float,
        entities: list[str] | None = None,
        embedding: list[float] | None = None,
        metadata: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> MemoryEntry:
        """Store an episodic memory with importance scoring."""
        entry_id = str(uuid.uuid4())
        now = timestamp or datetime.now(UTC)

        episodic_entry = EpisodicEntry(
            id=entry_id,
            content=content,
            timestamp=now,
            importance=max(0.0, min(1.0, importance)),
            entities=entities or [],
            embedding=embedding,
            metadata=metadata or {},
        )

        self._episodes[entry_id] = episodic_entry

        # Store in vector store if available
        if self.vector_store and embedding:
            safe_metadata = metadata or {}
            await self.vector_store.store(
                session_id=safe_metadata.get("session_id", "default"),
                user_message=content,
                assistant_message="",
                embedding=embedding,
                metadata={
                    "memory_id": entry_id,
                    "importance": importance,
                    "entities": entities or [],
                    **safe_metadata,
                },
            )

        return MemoryEntry(
            id=entry_id,
            content=content,
            memory_type=MemoryType.EPISODIC,
            timestamp=now,
            importance=importance,
            entities=entities or [],
            source="episodic_memory",
        )

    async def retrieve_relevant(
        self,
        query: str,
        query_embedding: list[float] | None = None,
        filter_dict: dict[str, Any] | None = None,
        top_k: int = 3,
    ) -> list[MemoryEntry]:
        """Retrieve relevant episodes with composite scoring."""
        candidates: list[tuple[EpisodicEntry, float]] = []

        # If vector store available, use it for initial retrieval
        if self.vector_store and query_embedding:
            try:
                vector_results = await self.vector_store.retrieve_relevant(
                    query=query,
                    query_embedding=query_embedding,
                    limit=top_k * 3,  # Get more candidates for ranking
                )
                # Map vector results to our entries
                for result in vector_results:
                    memory_id = (
                        result.metadata.get("memory_id") if hasattr(result, "metadata") else None
                    )
                    if memory_id and memory_id in self._episodes:
                        entry = self._episodes[memory_id]
                        similarity = 0.8  # Default high similarity from vector search
                        candidates.append((entry, similarity))
            except (RuntimeError, ValueError, TypeError):
                # Fall through to local search
                pass

        # If no candidates from vector store, search local episodes
        if not candidates:
            for entry in self._episodes.values():
                # Simple text matching similarity (fallback)
                similarity = self._calculate_text_similarity(query, entry.content)
                candidates.append((entry, similarity))

        # Apply filters if specified
        if filter_dict:
            filtered_candidates = []
            for entry, similarity in candidates:
                match = True
                if "entities" in filter_dict:
                    if not any(e in entry.entities for e in filter_dict["entities"]):
                        match = False
                if "min_importance" in filter_dict:
                    if entry.importance < filter_dict["min_importance"]:
                        match = False
                if match:
                    filtered_candidates.append((entry, similarity))
            candidates = filtered_candidates

        # Calculate composite scores and rank
        scored_entries: list[tuple[EpisodicEntry, float]] = []
        for entry, similarity in candidates:
            composite_score = self._calculate_composite_score(entry, similarity)
            scored_entries.append((entry, composite_score))

        # Sort by composite score descending
        scored_entries.sort(key=lambda x: x[1], reverse=True)

        # Convert to MemoryEntry and update access stats
        results: list[MemoryEntry] = []
        for entry, _score in scored_entries[:top_k]:
            entry.access_count += 1
            entry.last_accessed = datetime.now(UTC)

            results.append(
                MemoryEntry(
                    id=entry.id,
                    content=entry.content,
                    memory_type=MemoryType.EPISODIC,
                    timestamp=entry.timestamp,
                    importance=entry.importance,
                    entities=entry.entities,
                    relationships=entry.metadata.get("relationships", {}),
                    source="episodic_memory",
                    access_count=entry.access_count,
                    last_accessed=entry.last_accessed,
                )
            )

        return results

    def _calculate_composite_score(
        self,
        memory: EpisodicEntry,
        similarity: float,
    ) -> float:
        """Calculate composite score: semantic * importance * recency_decay."""
        # Time decay factor (exponential decay)
        age = datetime.now(UTC) - memory.timestamp
        age_days = age.total_seconds() / (24 * 3600)
        decay_factor = 0.5 ** (age_days / self.DECAY_HALF_LIFE_DAYS)

        # Recency boost for very recent memories (last hour)
        recency_boost = 1.0
        if age < timedelta(hours=1):
            recency_boost = 1.2
        elif age < timedelta(hours=24):
            recency_boost = 1.1

        # Access frequency boost (frequently accessed memories are more important)
        access_boost = 1.0 + (0.05 * min(memory.access_count, 5))

        # Composite: similarity x importance x decay x boosts
        composite = similarity * memory.importance * decay_factor * recency_boost * access_boost

        return round(composite, 4)

    def _calculate_text_similarity(self, query: str, content: str) -> float:
        """Calculate simple text similarity (fallback when no embeddings)."""
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())

        if not query_words:
            return 0.0

        overlap = len(query_words & content_words)
        return overlap / len(query_words)

    def get_episodes_by_entity(self, entity: str) -> list[MemoryEntry]:
        """Get all episodes related to a specific entity."""
        results: list[MemoryEntry] = []
        for entry in self._episodes.values():
            if entity in entry.entities:
                results.append(
                    MemoryEntry(
                        id=entry.id,
                        content=entry.content,
                        memory_type=MemoryType.EPISODIC,
                        timestamp=entry.timestamp,
                        importance=entry.importance,
                        entities=entry.entities,
                        source="episodic_memory",
                    )
                )
        return sorted(results, key=lambda m: m.timestamp, reverse=True)


__all__ = ["EpisodicEntry", "EpisodicMemory", "VectorStoreProtocol"]
