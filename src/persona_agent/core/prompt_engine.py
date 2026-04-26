"""Layered Prompt Engine with RoleRAG integration.

This module implements the three-layer prompt architecture:
- Layer 1: Core Identity (Static) - Character's unchanging identity
- Layer 2: Dynamic Context - Emotional, social, cognitive states
- Layer 3: Knowledge & Task - Context-aware knowledge retrieval

RoleRAG integration provides boundary-aware knowledge retrieval with
entity classification (out-of-scope/specific/general).

Inspired by:
- CrewAI: Role/goal/backstory triad with composite scoring
- RoleRAG: Entity normalization and boundary-aware retrieval
- Honcho: User modeling and dialectic memory
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Protocol

from persona_agent.core.schemas import (
    CoreIdentity,
    DynamicContext,
    KnowledgeBoundary,
    KnowledgeContext,
    LayeredPrompt,
    MemoryEntry,
    RetrievedKnowledge,
    SemanticMemory,
    TaskContext,
)
from persona_agent.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


# ============================================================================
# Entity Classification Types
# ============================================================================


class EntityType(Enum):
    """Classification of entities for boundary-aware retrieval.

    Based on RoleRAG research:
    - OUT_OF_SCOPE: Entity definitely not known to the character
    - SPECIFIC: Character-specific entity (e.g., character's family)
    - GENERAL: General knowledge entity (e.g., common concepts)
    """

    OUT_OF_SCOPE = auto()  # Entity definitely unknown to character
    SPECIFIC = auto()  # Character-specific knowledge
    GENERAL = auto()  # General knowledge


# ============================================================================
# RoleRAG Data Structures
# ============================================================================


@dataclass
class ClassifiedEntity:
    """An entity with its classification."""

    name: str
    entity_type: EntityType
    confidence: float = 0.0
    explanation: str = ""


@dataclass
class RetrievalResult:
    """Result from RoleRAG retrieval."""

    query: str
    hypothetical_context: str = ""
    extracted_entities: list[ClassifiedEntity] = field(default_factory=list)
    retrieved_knowledge: list[RetrievedKnowledge] = field(default_factory=list)
    boundary_status: str = "within"  # within, partial, out_of_scope
    confidence_score: float = 0.0


# ============================================================================
# Knowledge Graph Interface
# ============================================================================


class KnowledgeGraph(Protocol):
    """Protocol for knowledge graph implementations.

    Provides entity and relationship storage for RoleRAG retrieval.
    """

    def query_entity(self, entity: str) -> dict[str, Any]:
        """Query information about an entity."""
        ...

    def query_relationships(self, entity: str) -> dict[str, str]:
        """Query relationships for an entity."""
        ...

    def search_similar(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Search for similar entities/concepts."""
        ...

    def get_character_knowledge(self, character_name: str, domain: str) -> list[str]:
        """Get character-specific knowledge for a domain."""
        ...


# ============================================================================
# Hierarchical Memory System
# ============================================================================


class HierarchicalMemory:
    """Hierarchical memory system for RoleRAG.

    Combines working, episodic, and semantic memory for comprehensive
    context retrieval.
    """

    def __init__(
        self,
        semantic_memory: SemanticMemory | None = None,
        max_working_memory: int = 5,
    ):
        """Initialize hierarchical memory.

        Args:
            semantic_memory: Semantic memory for facts and relationships
            max_working_memory: Maximum entries in working memory
        """
        self.semantic_memory = semantic_memory or SemanticMemory()
        self.working_memory: list[MemoryEntry] = []
        self.max_working_memory = max_working_memory
        self.episodic_buffer: list[MemoryEntry] = []

    def add_to_working(self, entry: MemoryEntry) -> None:
        """Add entry to working memory.

        Args:
            entry: Memory entry to add
        """
        self.working_memory.append(entry)
        if len(self.working_memory) > self.max_working_memory:
            # Move oldest to episodic buffer
            oldest = self.working_memory.pop(0)
            self.episodic_buffer.append(oldest)

    def query_semantic(self, entity: str) -> dict[str, Any]:
        """Query semantic memory for entity.

        Args:
            entity: Entity name to query

        Returns:
            Entity information dict
        """
        return self.semantic_memory.query_entity(entity)

    def get_working_context(self) -> str:
        """Get working memory as context string.

        Returns:
            Formatted working memory context
        """
        if not self.working_memory:
            return ""

        lines = ["## Recent Context"]
        for entry in self.working_memory[-3:]:
            lines.append(f"- {entry.content}")
        return "\n".join(lines)

    def retrieve_relevant_episodes(self, query: str, top_k: int = 3) -> list[MemoryEntry]:
        """Retrieve relevant episodic memories.

        Args:
            query: Search query
            top_k: Maximum number of episodes

        Returns:
            List of relevant memory entries
        """
        # Simple keyword matching - production would use embeddings
        keywords = set(query.lower().split())
        scored = []

        for entry in self.episodic_buffer:
            score = sum(1 for kw in keywords if kw in entry.content.lower())
            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]


# ============================================================================
# RoleRAG Retriever
# ============================================================================


class RoleRAGRetriever:
    """RoleRAG knowledge retrieval with boundary awareness.

    Implements three-stage retrieval:
    1. Generate hypothetical context for the query
    2. Extract and classify entities (out-of-scope/specific/general)
    3. Retrieve appropriate knowledge based on classification

    Boundary-aware retrieval ensures characters only respond with
    knowledge they would realistically have.
    """

    def __init__(
        self,
        knowledge_graph: KnowledgeGraph | None = None,
        memory: HierarchicalMemory | None = None,
        llm_client: LLMClient | None = None,
    ):
        """Initialize RoleRAG retriever.

        Args:
            knowledge_graph: Knowledge graph for entity relationships
            memory: Hierarchical memory system
            llm_client: LLM client for entity classification
        """
        self.knowledge_graph = knowledge_graph
        self.memory = memory or HierarchicalMemory()
        self.llm_client = llm_client

        # Cache for entity classifications
        self._classification_cache: dict[tuple[str, str], ClassifiedEntity] = {}

    async def retrieve(
        self,
        query: str,
        character_name: str,
        knowledge_boundary: KnowledgeBoundary | None = None,
    ) -> RetrievalResult:
        """Execute three-stage RoleRAG retrieval.

        Stage 1: Generate hypothetical context
        Stage 2: Extract and classify entities
        Stage 3: Retrieve knowledge based on classification

        Args:
            query: User query to process
            character_name: Name of the character
            knowledge_boundary: Character's knowledge boundaries

        Returns:
            RetrievalResult with retrieved knowledge and metadata
        """
        result = RetrievalResult(query=query)

        try:
            # Stage 1: Generate hypothetical context
            result.hypothetical_context = await self._generate_hypothetical_context(
                query, character_name
            )

            # Stage 2: Extract and classify entities
            entities = await self._extract_entities(result.hypothetical_context, character_name)
            result.extracted_entities = entities

            # Stage 3: Retrieve knowledge based on entity types
            retrieved = await self._retrieve_by_classification(
                entities, character_name, knowledge_boundary
            )
            result.retrieved_knowledge = retrieved

            # Calculate overall confidence and boundary status
            result.confidence_score = self._calculate_confidence(entities, retrieved)
            result.boundary_status = self._determine_boundary_status(entities)

        except (ValueError, RuntimeError) as e:
            logger.error(f"RoleRAG retrieval failed: {e}")
            # Return empty result on failure
            result.boundary_status = "error"

        return result

    async def classify_entity(
        self,
        entity: str,
        character_name: str,
        knowledge_boundary: KnowledgeBoundary | None = None,
    ) -> ClassifiedEntity:
        """Classify an entity for boundary awareness.

        Classification hierarchy:
        1. Check if entity is in character's known domains/entities -> SPECIFIC
        2. Check if entity is in character's unknown domains -> OUT_OF_SCOPE
        3. Use LLM to classify ambiguous cases

        Args:
            entity: Entity name to classify
            character_name: Name of the character
            knowledge_boundary: Character's knowledge boundaries

        Returns:
            ClassifiedEntity with type and confidence
        """
        cache_key = (entity.lower(), character_name)
        if cache_key in self._classification_cache:
            return self._classification_cache[cache_key]

        # Check explicit boundaries first
        if knowledge_boundary:
            entity_lower = entity.lower()

            # Check known entities (exact or partial match)
            for known in knowledge_boundary.known_entities:
                if entity_lower in known.lower() or known.lower() in entity_lower:
                    classified = ClassifiedEntity(
                        name=entity,
                        entity_type=EntityType.SPECIFIC,
                        confidence=0.9,
                        explanation=f"Entity '{entity}' is in character's known entities",
                    )
                    self._classification_cache[cache_key] = classified
                    return classified

            # Check known domains
            for domain in knowledge_boundary.known_domains:
                if domain.lower() in entity_lower or entity_lower in domain.lower():
                    classified = ClassifiedEntity(
                        name=entity,
                        entity_type=EntityType.SPECIFIC,
                        confidence=0.8,
                        explanation=f"Entity '{entity}' matches known domain '{domain}'",
                    )
                    self._classification_cache[cache_key] = classified
                    return classified

            # Check unknown domains (out of scope)
            for unknown in knowledge_boundary.unknown_domains:
                if unknown.lower() in entity_lower or entity_lower in unknown.lower():
                    classified = ClassifiedEntity(
                        name=entity,
                        entity_type=EntityType.OUT_OF_SCOPE,
                        confidence=0.9,
                        explanation=f"Entity '{entity}' matches unknown domain '{unknown}'",
                    )
                    self._classification_cache[cache_key] = classified
                    return classified

        # Check knowledge graph if available
        if self.knowledge_graph:
            kg_info = self.knowledge_graph.query_entity(entity)
            if kg_info.get("fact"):
                # Entity exists in knowledge graph
                classified = ClassifiedEntity(
                    name=entity,
                    entity_type=EntityType.SPECIFIC,
                    confidence=0.85,
                    explanation=f"Entity '{entity}' found in knowledge graph",
                )
                self._classification_cache[cache_key] = classified
                return classified

        # Check semantic memory
        semantic_info = self.memory.query_semantic(entity)
        if semantic_info.get("fact"):
            classified = ClassifiedEntity(
                name=entity,
                entity_type=EntityType.SPECIFIC,
                confidence=0.8,
                explanation=f"Entity '{entity}' found in semantic memory",
            )
            self._classification_cache[cache_key] = classified
            return classified

        # Fall back to LLM classification if available
        if self.llm_client:
            llm_classified = await self._llm_classify_entity(entity, character_name)
            self._classification_cache[cache_key] = llm_classified
            return llm_classified

        # Default to GENERAL for unknown entities
        classified = ClassifiedEntity(
            name=entity,
            entity_type=EntityType.GENERAL,
            confidence=0.5,
            explanation=f"Entity '{entity}' not found in any source, defaulting to GENERAL",
        )
        self._classification_cache[cache_key] = classified
        return classified

    async def _generate_hypothetical_context(self, query: str, character_name: str) -> str:
        """Generate hypothetical context for a query.

        Uses LLM to generate what context would be helpful for answering
        the query in character.

        Args:
            query: User query
            character_name: Character name for context

        Returns:
            Hypothetical context string
        """
        if not self.llm_client:
            return query

        try:
            prompt = f"""Given the query "{query}", what background context and entities would {character_name} need to know about to respond appropriately?

Provide a brief summary (2-3 sentences) of the key entities and concepts mentioned or implied."""

            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that generates context for character role-playing.",
                },
                {"role": "user", "content": prompt},
            ]

            response = await self.llm_client.chat(messages, temperature=0.3)
            return response.content.strip()
        except (ValueError, RuntimeError) as e:
            logger.warning(f"Failed to generate hypothetical context: {e}")
            return query

    async def _extract_entities(self, text: str, character_name: str) -> list[ClassifiedEntity]:
        """Extract and classify entities from text.

        Args:
            text: Text to extract entities from
            character_name: Character name for classification

        Returns:
            List of classified entities
        """
        # Simple regex-based entity extraction
        # Production would use proper NER (spaCy, etc.)
        entity_pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b"
        potential_entities = set(re.findall(entity_pattern, text))

        # Add common named entities (simplified)
        words = text.split()
        for word in words:
            # Capitalized words might be entities
            if word[0].isupper() if word else False:
                potential_entities.add(word.strip(".,!?;:"))

        classified = []
        for entity in potential_entities:
            if len(entity) > 2:  # Filter out very short matches
                classification = await self.classify_entity(entity, character_name)
                classified.append(classification)

        return classified

    async def _retrieve_by_classification(
        self,
        entities: list[ClassifiedEntity],
        character_name: str,
        knowledge_boundary: KnowledgeBoundary | None = None,
    ) -> list[RetrievedKnowledge]:
        """Retrieve knowledge based on entity classifications.

        Args:
            entities: Classified entities
            character_name: Character name
            knowledge_boundary: Knowledge boundaries

        Returns:
            List of retrieved knowledge
        """
        retrieved: list[RetrievedKnowledge] = []

        for entity in entities:
            if entity.entity_type == EntityType.OUT_OF_SCOPE:
                # Skip out-of-scope entities
                continue

            if entity.entity_type == EntityType.SPECIFIC:
                # Retrieve specific character knowledge
                specific = await self._retrieve_specific_knowledge(entity.name, character_name)
                retrieved.extend(specific)

            elif entity.entity_type == EntityType.GENERAL:
                # Retrieve general knowledge (limited)
                general = await self._retrieve_general_knowledge(entity.name, knowledge_boundary)
                retrieved.extend(general)

        # Add working memory context
        working_context = self.memory.get_working_context()
        if working_context:
            retrieved.append(
                RetrievedKnowledge(
                    content=working_context,
                    source="working_memory",
                    relevance_score=0.7,
                    knowledge_type="context",
                )
            )

        # Deduplicate and sort by relevance
        seen = set()
        unique_retrieved = []
        for k in retrieved:
            key = (k.content, k.source)
            if key not in seen:
                seen.add(key)
                unique_retrieved.append(k)

        unique_retrieved.sort(key=lambda x: x.relevance_score, reverse=True)
        return unique_retrieved[:5]  # Return top 5

    async def _retrieve_specific_knowledge(
        self, entity: str, character_name: str
    ) -> list[RetrievedKnowledge]:
        """Retrieve specific character knowledge.

        Args:
            entity: Entity name
            character_name: Character name

        Returns:
            List of retrieved knowledge
        """
        retrieved: list[RetrievedKnowledge] = []

        # Query knowledge graph
        if self.knowledge_graph:
            kg_info = self.knowledge_graph.query_entity(entity)
            if kg_info.get("fact"):
                retrieved.append(
                    RetrievedKnowledge(
                        content=kg_info["fact"],
                        source="knowledge_graph",
                        relevance_score=0.9,
                        knowledge_type="fact",
                    )
                )

            relationships = self.knowledge_graph.query_relationships(entity)
            for rel, target in relationships.items():
                retrieved.append(
                    RetrievedKnowledge(
                        content=f"{entity} {rel} {target}",
                        source="knowledge_graph",
                        relevance_score=0.85,
                        knowledge_type="relationship",
                    )
                )

        # Query semantic memory
        semantic_info = self.memory.query_semantic(entity)
        if semantic_info.get("fact"):
            retrieved.append(
                RetrievedKnowledge(
                    content=semantic_info["fact"],
                    source="semantic_memory",
                    relevance_score=0.8,
                    knowledge_type="fact",
                )
            )

        return retrieved

    async def _retrieve_general_knowledge(
        self, entity: str, knowledge_boundary: KnowledgeBoundary | None = None
    ) -> list[RetrievedKnowledge]:
        """Retrieve general knowledge (with limits).

        Args:
            entity: Entity name
            knowledge_boundary: Knowledge boundaries

        Returns:
            List of retrieved knowledge
        """
        # Only retrieve general knowledge if character has relevant domain
        if knowledge_boundary:
            entity_lower = entity.lower()
            has_relevant_domain = any(
                domain.lower() in entity_lower or entity_lower in domain.lower()
                for domain in knowledge_boundary.known_domains
            )

            if not has_relevant_domain:
                # Character wouldn't know about this
                return []

        # Limited general knowledge retrieval
        retrieved: list[RetrievedKnowledge] = []

        # Only get basic facts from semantic memory
        semantic_info = self.memory.query_semantic(entity)
        if semantic_info.get("fact"):
            retrieved.append(
                RetrievedKnowledge(
                    content=semantic_info["fact"],
                    source="semantic_memory",
                    relevance_score=0.6,  # Lower score for general knowledge
                    knowledge_type="general_fact",
                )
            )

        return retrieved

    async def _llm_classify_entity(self, entity: str, character_name: str) -> ClassifiedEntity:
        """Use LLM to classify an ambiguous entity.

        Args:
            entity: Entity name
            character_name: Character name

        Returns:
            ClassifiedEntity
        """
        if not self.llm_client:
            return ClassifiedEntity(
                name=entity,
                entity_type=EntityType.GENERAL,
                confidence=0.5,
                explanation="No LLM available for classification",
            )

        try:
            prompt = f"""Classify the entity "{entity}" for the character {character_name}.

Categories:
- SPECIFIC: Character would definitely know about this (personal experiences, their world, etc.)
- GENERAL: Common knowledge that most people would know
- OUT_OF_SCOPE: Character would not know about this (other universes, future events, etc.)

Respond with ONLY: SPECIFIC, GENERAL, or OUT_OF_SCOPE"""

            messages = [
                {
                    "role": "system",
                    "content": "You classify entities for role-playing. Respond with only one word.",
                },
                {"role": "user", "content": prompt},
            ]

            response = await self.llm_client.chat(messages, temperature=0.1)
            result = response.content.strip().upper()

            if "OUT_OF_SCOPE" in result or "OUTOFSCOPE" in result:
                return ClassifiedEntity(
                    name=entity,
                    entity_type=EntityType.OUT_OF_SCOPE,
                    confidence=0.75,
                    explanation=f"LLM classified '{entity}' as OUT_OF_SCOPE",
                )
            elif "SPECIFIC" in result:
                return ClassifiedEntity(
                    name=entity,
                    entity_type=EntityType.SPECIFIC,
                    confidence=0.75,
                    explanation=f"LLM classified '{entity}' as SPECIFIC",
                )
            else:
                return ClassifiedEntity(
                    name=entity,
                    entity_type=EntityType.GENERAL,
                    confidence=0.75,
                    explanation=f"LLM classified '{entity}' as GENERAL",
                )
        except (ValueError, RuntimeError) as e:
            logger.warning(f"LLM classification failed for '{entity}': {e}")
            return ClassifiedEntity(
                name=entity,
                entity_type=EntityType.GENERAL,
                confidence=0.5,
                explanation="Classification failed, defaulting to GENERAL",
            )

    def _calculate_confidence(
        self, entities: list[ClassifiedEntity], retrieved: list[RetrievedKnowledge]
    ) -> float:
        """Calculate overall retrieval confidence.

        Args:
            entities: Classified entities
            retrieved: Retrieved knowledge

        Returns:
            Confidence score (0.0 - 1.0)
        """
        if not entities:
            return 0.5

        # Average entity classification confidence
        entity_conf = sum(e.confidence for e in entities) / len(entities)

        # Knowledge retrieval score
        if retrieved:
            knowledge_conf = sum(k.relevance_score for k in retrieved) / len(retrieved)
        else:
            knowledge_conf = 0.5

        # Weighted combination
        return 0.4 * entity_conf + 0.6 * knowledge_conf

    def _determine_boundary_status(self, entities: list[ClassifiedEntity]) -> str:
        """Determine overall boundary status.

        Args:
            entities: Classified entities

        Returns:
            Boundary status string
        """
        if not entities:
            return "within"

        out_of_scope_count = sum(1 for e in entities if e.entity_type == EntityType.OUT_OF_SCOPE)
        specific_count = sum(1 for e in entities if e.entity_type == EntityType.SPECIFIC)

        if out_of_scope_count == len(entities):
            return "out_of_scope"
        elif out_of_scope_count > 0:
            return "partial"
        elif specific_count > 0:
            return "specific"
        else:
            return "within"


# ============================================================================
# Layered Prompt Engine
# ============================================================================


class LayeredPromptEngine:
    """Three-layer prompt engine with RoleRAG integration.

    Builds prompts using three layers:
    - Layer 1 (Core Identity): Static character definition
    - Layer 2 (Dynamic Context): Emotional, social, cognitive states
    - Layer 3 (Knowledge & Task): Boundary-aware knowledge retrieval

    Integrates with RoleRAG for context-aware knowledge retrieval.
    """

    def __init__(
        self,
        core_identity: CoreIdentity,
        knowledge_graph: KnowledgeGraph | None = None,
        memory: HierarchicalMemory | None = None,
        llm_client: LLMClient | None = None,
        knowledge_boundary: KnowledgeBoundary | None = None,
        few_shot_examples: list[dict[str, str]] | None = None,
    ):
        """Initialize layered prompt engine.

        Args:
            core_identity: Static core identity
            knowledge_graph: Optional knowledge graph
            memory: Optional hierarchical memory
            llm_client: Optional LLM client for RoleRAG
            knowledge_boundary: Character's knowledge boundaries
            few_shot_examples: Examples for consistency
        """
        self.core_identity = core_identity
        self.knowledge_boundary = knowledge_boundary or KnowledgeBoundary(confidence=0.8)
        self.few_shot_examples = few_shot_examples or []

        # Initialize RoleRAG retriever
        self.role_rag = RoleRAGRetriever(
            knowledge_graph=knowledge_graph,
            memory=memory or HierarchicalMemory(),
            llm_client=llm_client,
        )

        logger.info(f"LayeredPromptEngine initialized for '{core_identity.name}'")

    async def build_prompt(
        self,
        user_input: str,
        dynamic_context: DynamicContext,
        task_context: TaskContext | None = None,
    ) -> LayeredPrompt:
        """Build complete three-layer prompt.

        Args:
            user_input: User's input message
            dynamic_context: Current dynamic context
            task_context: Optional task context

        Returns:
            Complete LayeredPrompt
        """
        # Retrieve knowledge using RoleRAG
        retrieved_knowledge = await self._retrieve_role_rag_knowledge(
            user_input, self.core_identity.name
        )

        # Build knowledge context
        knowledge_context = KnowledgeContext(
            boundaries=self.knowledge_boundary,
            retrieved_knowledge=retrieved_knowledge,
            task=task_context or TaskContext(),
        )

        # Create layered prompt
        layered_prompt = LayeredPrompt(
            core_identity=self.core_identity,
            dynamic_context=dynamic_context,
            knowledge_context=knowledge_context,
            few_shot_examples=self.few_shot_examples,
        )

        return layered_prompt

    async def _retrieve_role_rag_knowledge(
        self, query: str, character_name: str
    ) -> list[RetrievedKnowledge]:
        """Retrieve knowledge with boundary awareness using RoleRAG.

        Args:
            query: User query
            character_name: Character name

        Returns:
            List of retrieved knowledge
        """
        try:
            result = await self.role_rag.retrieve(
                query=query,
                character_name=character_name,
                knowledge_boundary=self.knowledge_boundary,
            )

            logger.debug(
                f"RoleRAG retrieved {len(result.retrieved_knowledge)} items "
                f"for query: {query[:50]}..."
            )

            return result.retrieved_knowledge
        except (ValueError, RuntimeError) as e:
            logger.error(f"RoleRAG retrieval failed: {e}")
            return []

    def set_knowledge_boundary(self, boundary: KnowledgeBoundary) -> None:
        """Update knowledge boundary.

        Args:
            boundary: New knowledge boundary
        """
        self.knowledge_boundary = boundary
        logger.debug("Knowledge boundary updated")

    def add_few_shot_example(self, user_input: str, character_response: str) -> None:
        """Add a few-shot example for consistency.

        Args:
            user_input: Example user input
            character_response: Example character response
        """
        self.few_shot_examples.append(
            {
                "user": user_input,
                "response": character_response,
            }
        )

    def get_system_prompt(
        self,
        user_input: str,
        dynamic_context: DynamicContext,
        task_context: TaskContext | None = None,
    ) -> str:
        """Get system prompt string (synchronous version).

        Note: This is a convenience method that doesn't use RoleRAG.
        For full RoleRAG retrieval, use build_prompt().

        Args:
            user_input: User input
            dynamic_context: Dynamic context
            task_context: Optional task context

        Returns:
            System prompt string
        """
        # Create knowledge context without retrieval
        knowledge_context = KnowledgeContext(
            boundaries=self.knowledge_boundary,
            retrieved_knowledge=[],
            task=task_context or TaskContext(),
        )

        layered_prompt = LayeredPrompt(
            core_identity=self.core_identity,
            dynamic_context=dynamic_context,
            knowledge_context=knowledge_context,
            few_shot_examples=self.few_shot_examples,
        )

        return layered_prompt.to_system_prompt()


# ============================================================================
# Helper Functions
# ============================================================================


def create_layered_prompt_engine(
    character_profile: dict[str, Any],
    llm_client: LLMClient | None = None,
) -> LayeredPromptEngine:
    """Create a LayeredPromptEngine from a character profile dict.

    Args:
        character_profile: Character profile data
        llm_client: Optional LLM client

    Returns:
        Configured LayeredPromptEngine
    """
    # Build CoreIdentity from profile
    from persona_agent.core.schemas import BehavioralMatrix, CoreValues

    core_values_data = character_profile.get("core_values", {})
    if isinstance(core_values_data, dict):
        core_values = CoreValues(**core_values_data)
    else:
        core_values = CoreValues()

    behavioral_data = character_profile.get("behavioral_matrix", {})
    if isinstance(behavioral_data, dict):
        behavioral_matrix = BehavioralMatrix(**behavioral_data)
    else:
        behavioral_matrix = BehavioralMatrix()

    core_identity = CoreIdentity(
        name=character_profile.get("name", "Unknown"),
        version=character_profile.get("version", "1.0.0"),
        backstory=character_profile.get("backstory", ""),
        values=core_values,
        behavioral_matrix=behavioral_matrix,
    )

    # Build KnowledgeBoundary from profile
    knowledge_boundary = KnowledgeBoundary(
        known_domains=character_profile.get("knowledge_domains", []),
        known_entities=character_profile.get("known_entities", []),
        unknown_domains=character_profile.get("limitations", []),
        confidence=character_profile.get("knowledge_confidence", 0.8),
    )

    return LayeredPromptEngine(
        core_identity=core_identity,
        knowledge_boundary=knowledge_boundary,
        llm_client=llm_client,
    )


__all__ = [
    # Enums
    "EntityType",
    # Data classes
    "ClassifiedEntity",
    "RetrievalResult",
    # Classes
    "KnowledgeGraph",
    "HierarchicalMemory",
    "RoleRAGRetriever",
    "LayeredPromptEngine",
    # Functions
    "create_layered_prompt_engine",
]
