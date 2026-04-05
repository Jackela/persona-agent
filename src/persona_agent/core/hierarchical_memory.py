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
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol

try:
    import networkx as nx  # noqa: F401

    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False

from persona_agent.core.schemas import MemoryEntry, MemoryType


@dataclass
class Message:
    """A simple message structure."""

    role: str
    content: str


# ============================================================================
# Working Memory
# ============================================================================


class WorkingMemory:
    """Working memory - recent conversation context (3-5 exchanges).

    Working memory always stays in context and provides immediate
    access to the most recent conversation turns.

    Each exchange contains both user message and assistant response.
    """

    def __init__(self, max_size: int = 5):
        """Initialize working memory.

        Args:
            max_size: Maximum number of exchanges to keep (default: 5)
        """
        self.max_size = max_size
        self._exchanges: deque[dict[str, str]] = deque(maxlen=max_size)

    def add_exchange(self, user_msg: str, assistant_msg: str) -> None:
        """Add a conversation exchange to working memory.

        Args:
            user_msg: User's message
            assistant_msg: Assistant's response
        """
        self._exchanges.append(
            {
                "user": user_msg,
                "assistant": assistant_msg,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def get_recent(self, n: int | None = None) -> list[Message]:
        """Get recent messages from working memory.

        Args:
            n: Number of exchanges to retrieve. If None, returns all.

        Returns:
            List of Message objects (flattened user/assistant pairs)
        """
        if n is None or n > len(self._exchanges):
            n = len(self._exchanges)

        exchanges = list(self._exchanges)[-n:]
        messages: list[Message] = []

        for exchange in exchanges:
            messages.append(Message(role="user", content=exchange["user"]))
            messages.append(Message(role="assistant", content=exchange["assistant"]))

        return messages

    def to_prompt_context(self) -> str:
        """Format working memory for inclusion in prompt.

        Returns:
            Formatted string with recent conversation context
        """
        if not self._exchanges:
            return ""

        lines = ["## Recent Conversation"]
        for i, exchange in enumerate(self._exchanges, 1):
            lines.append(f"\n### Exchange {i}")
            lines.append(f"User: {exchange['user']}")
            lines.append(f"Assistant: {exchange['assistant']}")

        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all exchanges from working memory."""
        self._exchanges.clear()

    def __len__(self) -> int:
        """Return the number of exchanges in working memory."""
        return len(self._exchanges)


# ============================================================================
# Episodic Memory
# ============================================================================


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
    ) -> MemoryEntry:
        """Store an episodic memory with importance scoring.

        Args:
            content: The memory content
            importance: Importance score (0.0 to 1.0)
            entities: Related entities extracted from content
            embedding: Vector embedding for semantic search
            metadata: Additional metadata

        Returns:
            Created MemoryEntry
        """
        entry_id = str(uuid.uuid4())
        now = datetime.now()

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
        """Retrieve relevant episodes with composite scoring.

        Retrieves memories using:
        - Semantic similarity (if embedding provided)
        - Time decay weighting (older = less relevant)
        - Importance boosting (higher = more relevant)

        Args:
            query: Search query text
            query_embedding: Query vector embedding for semantic search
            filter_dict: Optional filters (e.g., {"entities": ["person"]}
            top_k: Number of top results to return

        Returns:
            List of relevant MemoryEntry objects
        """
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
            except Exception:
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
            entry.last_accessed = datetime.now()

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
        """Calculate composite score: semantic * importance * recency_decay.

        Args:
            memory: The episodic memory entry
            similarity: Semantic similarity score (0.0 to 1.0)

        Returns:
            Composite relevance score
        """
        # Time decay factor (exponential decay)
        age = datetime.now() - memory.timestamp
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

        # Composite: similarity × importance × decay × boosts
        composite = similarity * memory.importance * decay_factor * recency_boost * access_boost

        return round(composite, 4)

    def _calculate_text_similarity(self, query: str, content: str) -> float:
        """Calculate simple text similarity (fallback when no embeddings).

        Args:
            query: Search query
            content: Memory content

        Returns:
            Similarity score (0.0 to 1.0)
        """
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())

        if not query_words:
            return 0.0

        overlap = len(query_words & content_words)
        return overlap / len(query_words)

    def get_episodes_by_entity(self, entity: str) -> list[MemoryEntry]:
        """Get all episodes related to a specific entity.

        Args:
            entity: Entity to search for

        Returns:
            List of MemoryEntry objects containing the entity
        """
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


# ============================================================================
# Semantic Memory
# ============================================================================


class SemanticMemory:
    """Semantic memory - facts, concepts, and knowledge graph.

    Stores factual knowledge as a directed graph using NetworkX:
    - Nodes represent entities
    - Edges represent relationships (with predicate labels)
    - Supports entity queries and graph traversal
    """

    def __init__(self):
        """Initialize semantic memory with empty knowledge graph."""
        if not NETWORKX_AVAILABLE:
            raise ImportError(
                "NetworkX is required for SemanticMemory. Install with: pip install networkx"
            )

        import networkx as nx  # type: ignore

        self.graph: Any = nx.DiGraph()
        self._facts: dict[str, list[tuple[str, float]]] = {}  # entity -> [(fact, confidence)]

    def add_fact(self, entity: str, fact: str, confidence: float = 1.0) -> None:
        """Add a factual statement about an entity.

        Args:
            entity: The entity the fact is about
            fact: The factual statement
            confidence: Confidence level (0.0 to 1.0)
        """
        entity = entity.lower().strip()
        fact = fact.strip()
        confidence = max(0.0, min(1.0, confidence))

        # Add to facts dictionary
        if entity not in self._facts:
            self._facts[entity] = []
        self._facts[entity].append((fact, confidence))

        # Add entity as node in graph
        if entity not in self.graph:
            self.graph.add_node(entity, node_type="entity")

        # Add fact as a "has_fact" relationship
        fact_node = f"fact:{entity}:{len(self._facts[entity])}"
        self.graph.add_node(fact_node, node_type="fact", content=fact)
        self.graph.add_edge(
            entity,
            fact_node,
            predicate="has_fact",
            confidence=confidence,
        )

    def add_relationship(
        self,
        subject: str,
        predicate: str,
        obj: str,
        confidence: float = 1.0,
    ) -> None:
        """Add a relationship to the knowledge graph.

        Args:
            subject: Subject entity
            predicate: Relationship type (e.g., "likes", "knows")
            obj: Object entity
            confidence: Confidence level (0.0 to 1.0)
        """
        subject = subject.lower().strip()
        obj = obj.lower().strip()
        predicate = predicate.lower().strip()
        confidence = max(0.0, min(1.0, confidence))

        # Add nodes if they don't exist
        if subject not in self.graph:
            self.graph.add_node(subject, node_type="entity")
        if obj not in self.graph:
            self.graph.add_node(obj, node_type="entity")

        # Add edge with relationship metadata
        self.graph.add_edge(
            subject,
            obj,
            predicate=predicate,
            confidence=confidence,
            timestamp=datetime.now().isoformat(),
        )

    def query_entity(self, entity: str) -> dict[str, Any]:
        """Query all known information about an entity.

        Args:
            entity: Entity to query

        Returns:
            Dictionary with facts, relationships, and related entities
        """
        entity = entity.lower().strip()

        if entity not in self.graph:
            return {
                "entity": entity,
                "exists": False,
                "facts": [],
                "outgoing_relations": [],
                "incoming_relations": [],
            }

        # Get facts
        facts = self._facts.get(entity, [])

        # Get outgoing relationships
        outgoing = []
        if entity in self.graph:
            for _, target, data in self.graph.out_edges(entity, data=True):
                if data.get("predicate") != "has_fact":
                    outgoing.append(
                        {
                            "predicate": data.get("predicate", "related_to"),
                            "object": target,
                            "confidence": data.get("confidence", 1.0),
                        }
                    )

        # Get incoming relationships
        incoming = []
        if entity in self.graph:
            for source, _, data in self.graph.in_edges(entity, data=True):
                if data.get("predicate") != "has_fact":
                    incoming.append(
                        {
                            "subject": source,
                            "predicate": data.get("predicate", "related_to"),
                            "confidence": data.get("confidence", 1.0),
                        }
                    )

        return {
            "entity": entity,
            "exists": True,
            "facts": [{"fact": f, "confidence": c} for f, c in facts],
            "outgoing_relations": outgoing,
            "incoming_relations": incoming,
        }

    def extract_entities(self, text: str) -> list[str]:
        """Extract entities from text (simple rule-based NER).

        This is a simple implementation. For production, consider using:
        - spaCy NER
        - LLM-based extraction
        - Custom trained models

        Args:
            text: Input text

        Returns:
            List of extracted entity strings
        """
        # Simple pattern-based extraction
        entities: set[str] = set()

        # Capitalized words/phrases (potential proper nouns)
        # Pattern: Capitalized word followed by optional lowercase words
        proper_noun_pattern = r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b"
        for match in re.finditer(proper_noun_pattern, text):
            entity = match.group().lower()
            if len(entity) > 2:  # Filter out short matches
                entities.add(entity)

        # Known entity patterns
        patterns = [
            # "My name is X", "I am X", "Call me X"
            r"(?:my name is|i am|call me|this is)\s+([A-Z][a-z]+)",
            # "I live in X", "I'm from X"
            r"(?:live in|from|located in|based in)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            # "I work at X", "I study at X"
            r"(?:work at|study at|employed by|work for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                entities.add(match.group(1).lower())

        return sorted(entities)

    def get_related_entities(self, entity: str, depth: int = 1) -> list[str]:
        """Get entities related within N hops in the knowledge graph.

        Args:
            entity: Starting entity
            depth: Number of hops to traverse (default: 1)

        Returns:
            List of related entity names
        """
        entity = entity.lower().strip()

        if entity not in self.graph:
            return []

        related: set[str] = set()

        # Use BFS to find related entities up to depth
        visited: set[str] = {entity}
        current_level: set[str] = {entity}

        for _ in range(depth):
            next_level: set[str] = set()
            for node in current_level:
                # Outgoing edges
                for neighbor in self.graph.successors(node):
                    if neighbor not in visited:
                        # Skip fact nodes
                        if self.graph.nodes[neighbor].get("node_type") == "entity":
                            related.add(neighbor)
                            next_level.add(neighbor)
                        visited.add(neighbor)

                # Incoming edges
                for neighbor in self.graph.predecessors(node):
                    if neighbor not in visited:
                        if self.graph.nodes[neighbor].get("node_type") == "entity":
                            related.add(neighbor)
                            next_level.add(neighbor)
                        visited.add(neighbor)

            current_level = next_level
            if not current_level:
                break

        return sorted(related)

    def find_path(self, entity1: str, entity2: str) -> list[dict] | None:
        """Find relationship path between two entities.

        Args:
            entity1: Starting entity
            entity2: Target entity

        Returns:
            List of relationship steps, or None if no path exists
        """
        entity1 = entity1.lower().strip()
        entity2 = entity2.lower().strip()

        if entity1 not in self.graph or entity2 not in self.graph:
            return None

        try:
            import networkx as nx  # type: ignore

            path = nx.shortest_path(self.graph, entity1, entity2)
            relationships = []

            for i in range(len(path) - 1):
                source, target = path[i], path[i + 1]
                edge_data = self.graph.get_edge_data(source, target)
                relationships.append(
                    {
                        "from": source,
                        "to": target,
                        "predicate": (
                            edge_data.get("predicate", "related_to") if edge_data else "related_to"
                        ),
                    }
                )

            return relationships
        except Exception:
            return None

    def get_all_entities(self) -> list[str]:
        """Get all entities in the knowledge graph.

        Returns:
            List of all entity names
        """
        return [
            node for node, data in self.graph.nodes(data=True) if data.get("node_type") == "entity"
        ]


# ============================================================================
# Hierarchical Memory (Unified Interface)
# ============================================================================


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
        """Merge memories from all layers and calculate fusion score.

        Args:
            working: Working memory messages
            episodic: Episodic memory entries
            semantic: Semantic memory facts

        Returns:
            Merged MemoryContext with fusion score
        """
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
                "relations": self.semantic.graph.number_of_edges(),
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
