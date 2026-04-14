"""Hierarchical Memory System inspired by MemoryBank (Google Research 2024).

This module implements a three-layer memory architecture:
1. Working Memory - Recent conversation context (3-5 exchanges), always in context
2. Episodic Memory - Event-based experiences with vectorized semantic retrieval
3. Semantic Memory - Knowledge graph with entities and relationships

Key features:
- Time decay: Older memories lose importance (exponential decay)
- Importance scoring: User-emphasized content has higher weight
- Memory fusion: Combine all three layers with composite ranking
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from persona_agent.core.memory.episodic_memory import (
    EpisodicEntry,
    EpisodicMemory,
    VectorStoreProtocol,
)
from persona_agent.core.memory.semantic_memory import SemanticMemory
from persona_agent.core.memory.working_memory import Message, WorkingMemory
from persona_agent.core.schemas import MemoryEntry


@dataclass
class RetrievalContext:
    """Context for memory retrieval."""

    query_embedding: list[float] | None = None
    session_id: str | None = None
    top_k_working: int = 5
    top_k_episodic: int = 3
    top_k_semantic: int = 3
    include_entities: bool = True
    filter_importance: float | None = None


@dataclass
class MemoryContext:
    """Combined memory context from all three layers."""

    working_messages: list[Message] = field(default_factory=list)
    episodic_memories: list[MemoryEntry] = field(default_factory=list)
    semantic_facts: list[dict] = field(default_factory=list)
    related_entities: list[str] = field(default_factory=list)
    fusion_score: float = 0.0

    def to_prompt_context(self) -> str:
        """Convert memory context to prompt string."""
        lines = []

        # Working memory (always most important)
        if self.working_messages:
            lines.append("## Recent Conversation")
            for msg in self.working_messages:
                role = "User" if msg.role == "user" else "Assistant"
                lines.append(f"{role}: {msg.content}")
            lines.append("")

        # Episodic memories
        if self.episodic_memories:
            lines.append("## Relevant Past Experiences")
            for mem in self.episodic_memories:
                lines.append(f"- {mem.content}")
                if mem.entities:
                    lines.append(f"  (Related: {', '.join(mem.entities)})")
            lines.append("")

        # Semantic knowledge
        if self.semantic_facts:
            lines.append("## Known Facts")
            for fact_data in self.semantic_facts:
                entity = fact_data.get("entity", "Unknown")
                facts = fact_data.get("facts", [])
                if facts:
                    lines.append(f"About {entity}:")
                    for f in facts[:2]:  # Top 2 facts per entity
                        lines.append(f"  - {f['fact']}")
            lines.append("")

        return "\n".join(lines)


class HierarchicalMemory:
    """Unified interface for three-layer memory system.

    Coordinates:
    - Working Memory: Always included recent context
    - Episodic Memory: Event-based retrieval with semantic search
    - Semantic Memory: Knowledge graph queries

    Provides memory fusion and unified retrieval API.
    """

    def __init__(
        self,
        working_memory: WorkingMemory | None = None,
        episodic_memory: EpisodicMemory | None = None,
        semantic_memory: SemanticMemory | None = None,
    ):
        """Initialize hierarchical memory system.

        Args:
            working_memory: Working memory instance
            episodic_memory: Episodic memory instance
            semantic_memory: Semantic memory instance
        """
        self.working = working_memory or WorkingMemory()
        self.episodic = episodic_memory or EpisodicMemory()
        self.semantic = semantic_memory or SemanticMemory()

    async def retrieve(
        self,
        query: str,
        context: RetrievalContext | None = None,
    ) -> MemoryContext:
        """Retrieve memories from all three layers.

        Retrieval strategy:
        1. Always include working memory
        2. Semantic search episodic memory
        3. Query semantic memory for entities
        4. Merge and rank by relevance

        Args:
            query: Search query
            context: Retrieval context and parameters

        Returns:
            Combined MemoryContext from all layers
        """
        context = context or RetrievalContext()

        # 1. Working memory - always included
        working_messages = self.working.get_recent(context.top_k_working)

        # 2. Episodic memory - semantic retrieval
        filter_dict = None
        if context.filter_importance:
            filter_dict = {"min_importance": context.filter_importance}

        episodic_memories = await self.episodic.retrieve_relevant(
            query=query,
            query_embedding=context.query_embedding,
            filter_dict=filter_dict,
            top_k=context.top_k_episodic,
        )

        # 3. Semantic memory - entity-based retrieval
        semantic_facts: list[dict] = []
        related_entities: list[str] = []

        if context.include_entities:
            # Extract entities from query
            query_entities = self.semantic.extract_entities(query)

            # Also extract from episodic results
            for mem in episodic_memories:
                query_entities.extend(mem.entities)

            # Query each unique entity
            seen_entities: set[str] = set()
            for entity in query_entities:
                if entity not in seen_entities:
                    entity_info = self.semantic.query_entity(entity)
                    if entity_info.get("exists"):
                        semantic_facts.append(entity_info)
                        related_entities.extend(self.semantic.get_related_entities(entity, depth=1))
                        seen_entities.add(entity)

        # 4. Merge and rank
        memory_context = self._merge_and_rank(
            working=working_messages,
            episodic=episodic_memories,
            semantic=semantic_facts,
        )
        memory_context.related_entities = list(set(related_entities))

        return memory_context

    async def store_exchange(
        self,
        user_msg: str,
        assistant_msg: str,
        summary: str | None = None,
        importance: float = 0.5,
        embedding: list[float] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store conversation exchange across all layers.

        Storage strategy:
        1. Add to working memory (always)
        2. Create episodic memory if significant
        3. Extract and store entities in semantic memory

        Args:
            user_msg: User's message
            assistant_msg: Assistant's response
            summary: Optional summary for episodic memory
            importance: Importance score for episodic memory
            embedding: Vector embedding for episodic memory
            metadata: Additional metadata
        """
        # 1. Always store in working memory
        self.working.add_exchange(user_msg, assistant_msg)

        # 2. Create episodic memory if significant
        if summary or importance > 0.3:
            content = summary or f"User: {user_msg}\nAssistant: {assistant_msg}"

            # Extract entities for this episode
            entities = self.semantic.extract_entities(user_msg)
            entities.extend(self.semantic.extract_entities(assistant_msg))

            await self.episodic.store_episode(
                content=content,
                importance=importance,
                entities=list(set(entities)),
                embedding=embedding,
                metadata=metadata or {},
            )

        # 3. Extract and store semantic knowledge
        self._extract_and_store_semantic_knowledge(user_msg)
        self._extract_and_store_semantic_knowledge(assistant_msg)

    def _extract_and_store_semantic_knowledge(self, text: str) -> None:
        """Extract and store facts from text in semantic memory.

        Args:
            text: Text to extract knowledge from
        """
        # Simple pattern-based fact extraction
        # In production, this would use LLM-based extraction

        # Pattern: "X is Y"
        is_pattern = r"([A-Z][a-z]+(?:\s+[a-z]+){0,3})\s+is\s+([^.]+)"
        for match in re.finditer(is_pattern, text):
            entity, fact = match.groups()
            self.semantic.add_fact(entity.lower(), fact.strip(), confidence=0.7)

        # Pattern: "X likes Y"
        likes_pattern = r"([A-Z][a-z]+)\s+(likes?|enjoys?|prefers?)\s+([^.]+)"
        for match in re.finditer(likes_pattern, text, re.IGNORECASE):
            subject, verb, obj = match.groups()
            self.semantic.add_relationship(
                subject.lower(),
                "likes",
                obj.strip().lower(),
                confidence=0.6,
            )

    def _merge_and_rank(
        self,
        working: list[Message],
        episodic: list[MemoryEntry],
        semantic: list[dict],
    ) -> MemoryContext:
        """Merge memories from all layers and calculate fusion score."""
        # Calculate fusion score based on memory richness
        score = 0.0

        # Working memory contributes to recency score
        if working:
            score += min(len(working) * 0.1, 0.3)

        # Episodic memory contributes to experience depth
        if episodic:
            avg_importance = sum(m.importance for m in episodic) / len(episodic)
            score += min(avg_importance * 0.4, 0.4)

        # Semantic memory contributes to knowledge richness
        if semantic:
            fact_count = sum(len(s.get("facts", [])) for s in semantic)
            score += min(fact_count * 0.05, 0.3)

        return MemoryContext(
            working_messages=working,
            episodic_memories=episodic,
            semantic_facts=semantic,
            fusion_score=round(score, 2),
        )

    def export_graph(self) -> dict[str, list[dict]]:
        """Export semantic memory graph as Cytoscape.js-compatible JSON.

        Returns:
            Dictionary with nodes and edges in Cytoscape.js format
        """
        if self.semantic.graph is None:
            return {"nodes": [], "edges": []}

        nodes: list[dict] = []
        edges: list[dict] = []

        for node, data in self.semantic.graph.nodes(data=True):
            node_type = data.get("node_type", "entity")
            label = data.get("content", node) if node_type == "fact" else node
            nodes.append(
                {
                    "data": {
                        "id": node,
                        "label": label,
                        "type": node_type,
                    }
                }
            )

        for source, target, data in self.semantic.graph.edges(data=True):
            edges.append(
                {
                    "data": {
                        "source": source,
                        "target": target,
                        "label": data.get("predicate", "related_to"),
                        "confidence": data.get("confidence", 1.0),
                    }
                }
            )

        return {"nodes": nodes, "edges": edges}

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the memory system.

        Returns:
            Dictionary with memory statistics
        """
        return {
            "working": {
                "exchanges": len(self.working),
                "max_size": self.working.max_size,
            },
            "episodic": {
                "total_episodes": len(self.episodic._episodes),
            },
            "semantic": {
                "entities": len(self.semantic.get_all_entities()),
                "facts": sum(len(f) for f in self.semantic._facts.values()),
                "relations": (
                    self.semantic.graph.number_of_edges() if self.semantic.graph is not None else 0
                ),
            },
        }


__all__ = [
    "WorkingMemory",
    "EpisodicMemory",
    "EpisodicEntry",
    "SemanticMemory",
    "HierarchicalMemory",
    "RetrievalContext",
    "MemoryContext",
    "VectorStoreProtocol",
    "Message",
]
