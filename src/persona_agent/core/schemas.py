"""Core schemas for the new Persona-Agent architecture.

This module defines the base data models for:
- Three-layer prompt system
- Cognitive-emotional dual-path architecture
- Hierarchical memory system
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
from enum import Enum, auto
from typing import Any

from pydantic import BaseModel, Field, field_validator

# ============================================================================
# Layer 1: Core Identity (Static)
# ============================================================================


class CoreValues(BaseModel):
    """Character's core values and principles."""

    values: list[str] = Field(default_factory=list)
    fears: list[str] = Field(default_factory=list)
    desires: list[str] = Field(default_factory=list)
    boundaries: list[str] = Field(default_factory=list)


class BehavioralMatrix(BaseModel):
    """Behavioral patterns and constraints."""

    must_always: list[str] = Field(default_factory=list)
    must_never: list[str] = Field(default_factory=list)
    should_avoid: list[str] = Field(default_factory=list)


class CoreIdentity(BaseModel):
    """Static core identity - never changes during conversation."""

    name: str
    version: str = "1.0.0"
    backstory: str = ""
    values: CoreValues = Field(default_factory=CoreValues)
    behavioral_matrix: BehavioralMatrix = Field(default_factory=BehavioralMatrix)


# ============================================================================
# Layer 2: Dynamic Context (Emotional, Social, Cognitive States)
# ============================================================================


class EmotionalState(BaseModel):
    """Emotional state using valence-arousal model (Circumplex Model of Affect).

    Valence: Pleasantness (-1.0 to 1.0)
        -1.0 = Very negative (angry, sad, fearful)
        0.0 = Neutral
        1.0 = Very positive (happy, excited, content)

    Arousal: Activation level (0.0 to 1.0)
        0.0 = Sleepy, relaxed, calm
        0.5 = Neutral
        1.0 = Excited, alert, intense

    Dominance: Sense of control (0.0 to 1.0)
        0.0 = Submissive, controlled
        0.5 = Neutral
        1.0 = Dominant, in-control
    """

    valence: float = Field(0.0, ge=-1.0, le=1.0)
    arousal: float = Field(0.5, ge=0.0, le=1.0)
    dominance: float = Field(0.5, ge=0.0, le=1.0)

    # Emotional labels for reference (not mutually exclusive)
    primary_emotion: str = "neutral"
    secondary_emotions: list[str] = Field(default_factory=list)

    # Temporal dynamics
    intensity: float = Field(0.5, ge=0.0, le=1.0)
    entered_at: datetime = Field(default_factory=datetime.now)
    duration_seconds: float = 0.0

    @field_validator("secondary_emotions", mode="before")
    @classmethod
    def validate_secondary_emotions(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return list(v)


class RelationshipState(BaseModel):
    """Social relationship state between character and user."""

    intimacy: float = Field(0.3, ge=0.0, le=1.0)  # Closeness
    trust: float = Field(0.5, ge=0.0, le=1.0)  # Trust level
    respect: float = Field(0.5, ge=0.0, le=1.0)  # Respect level
    familiarity: float = Field(0.0, ge=0.0, le=1.0)  # How well they know each other

    # Relationship dynamics
    current_stage: str = "initial"
    interaction_count: int = 0
    last_interaction_at: datetime | None = None


class CognitiveState(BaseModel):
    """Cognitive state of the character."""

    # Attention focus
    focus_target: str = "user"  # What/who the character is focusing on
    attention_level: float = Field(0.8, ge=0.0, le=1.0)

    # Current goals and intentions
    active_goals: list[str] = Field(default_factory=list)
    current_intention: str = ""

    # Mental load
    cognitive_load: float = Field(0.3, ge=0.0, le=1.0)  # How mentally taxed they are


class DynamicContext(BaseModel):
    """Dynamic context that changes during conversation (Layer 2)."""

    emotional: EmotionalState = Field(
        default_factory=lambda: EmotionalState(
            valence=0.0, arousal=0.5, dominance=0.5, intensity=0.5
        )
    )
    social: RelationshipState = Field(
        default_factory=lambda: RelationshipState(
            intimacy=0.3, trust=0.3, respect=0.5, familiarity=0.2
        )
    )
    cognitive: CognitiveState = Field(
        default_factory=lambda: CognitiveState(
            attention_level=0.8, cognitive_load=0.3
        )
    )

    # Conversation context
    conversation_turn: int = 0
    topic: str = ""
    user_intent: str = ""


# ============================================================================
# Layer 3: Knowledge & Task Context
# ============================================================================


class KnowledgeBoundary(BaseModel):
    """Defines what the character knows and doesn't know."""

    # Domains the character has knowledge in
    known_domains: list[str] = Field(default_factory=list)

    # Specific facts/entities the character knows about
    known_entities: list[str] = Field(default_factory=list)

    # Things the character definitely doesn't know
    unknown_domains: list[str] = Field(default_factory=list)

    # Confidence level in knowledge (0.0 = uncertain, 1.0 = certain)
    confidence: float = Field(0.8, ge=0.0, le=1.0)


def _default_knowledge_boundary() -> KnowledgeBoundary:
    return KnowledgeBoundary(known_domains=[], known_entities=[], unknown_domains=[], confidence=0.8)


class RetrievedKnowledge(BaseModel):
    """Knowledge retrieved from RoleRAG system."""

    content: str
    source: str
    relevance_score: float = Field(0.0, ge=0.0, le=1.0)
    knowledge_type: str = "fact"  # fact, memory, preference, etc.


class TaskContext(BaseModel):
    """Current task and constraints."""

    task_type: str = "conversation"
    instructions: str = ""
    constraints: list[str] = Field(default_factory=list)
    expected_output_format: str = ""


class KnowledgeContext(BaseModel):
    """Knowledge and task context (Layer 3)."""

    boundaries: KnowledgeBoundary = Field(default_factory=_default_knowledge_boundary)
    retrieved_knowledge: list[RetrievedKnowledge] = Field(default_factory=list)
    task: TaskContext = Field(default_factory=TaskContext)


# ============================================================================
# Three-Layer Prompt System
# ============================================================================


class LayeredPrompt(BaseModel):
    """Complete three-layer prompt structure."""

    # Layer 1: Static core identity
    core_identity: CoreIdentity

    # Layer 2: Dynamic context
    dynamic_context: DynamicContext

    # Layer 3: Knowledge and task
    knowledge_context: KnowledgeContext

    # Few-shot examples for consistency
    few_shot_examples: list[dict[str, str]] = Field(default_factory=list)

    def to_system_prompt(self) -> str:
        """Convert to a complete system prompt string."""
        lines = []

        # Layer 1: Core Identity
        lines.append("# Core Identity")
        lines.append(f"You are {self.core_identity.name}.")
        if self.core_identity.backstory:
            lines.append("\n## Backstory")
            lines.append(self.core_identity.backstory)

        if self.core_identity.values.values:
            lines.append("\n## Core Values")
            for value in self.core_identity.values.values:
                lines.append(f"- {value}")

        if self.core_identity.behavioral_matrix.must_always:
            lines.append("\n## Must Always")
            for item in self.core_identity.behavioral_matrix.must_always:
                lines.append(f"- {item}")

        if self.core_identity.behavioral_matrix.must_never:
            lines.append("\n## Must Never")
            for item in self.core_identity.behavioral_matrix.must_never:
                lines.append(f"- {item}")

        # Layer 2: Dynamic Context
        lines.append("\n# Current State")

        # Emotional state
        emotional = self.dynamic_context.emotional
        lines.append("\n## Emotional State")
        lines.append(f"- Primary emotion: {emotional.primary_emotion}")
        lines.append(f"- Valence: {emotional.valence:.2f} (-1=negative, +1=positive)")
        lines.append(f"- Arousal: {emotional.arousal:.2f} (0=calm, 1=excited)")
        lines.append(f"- Intensity: {emotional.intensity:.2f}")

        # Social state
        social = self.dynamic_context.social
        lines.append("\n## Relationship")
        lines.append(f"- Intimacy: {social.intimacy:.2f}")
        lines.append(f"- Trust: {social.trust:.2f}")
        lines.append(f"- Stage: {social.current_stage}")

        # Layer 3: Knowledge & Task
        if self.knowledge_context.retrieved_knowledge:
            lines.append("\n# Relevant Knowledge")
            for knowledge in self.knowledge_context.retrieved_knowledge[:3]:
                lines.append(f"- [{knowledge.source}]: {knowledge.content}")

        if self.knowledge_context.task.instructions:
            lines.append("\n# Task")
            lines.append(self.knowledge_context.task.instructions)

        if self.knowledge_context.boundaries.known_domains:
            lines.append("\n# Knowledge Domains")
            lines.append(
                f"You know about: {', '.join(self.knowledge_context.boundaries.known_domains)}"
            )

        return "\n".join(lines)


# ============================================================================
# Cognitive-Emotional Processing
# ============================================================================


class CognitiveOutput(BaseModel):
    """Output from cognitive processing pathway."""

    understanding: str = ""  # What the character understood
    relevance_score: float = Field(0.5, ge=0.0, le=1.0)
    user_intent: str = ""
    topics: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    reasoning: str = ""  # Internal reasoning


class EmotionalOutput(BaseModel):
    """Output from emotional processing pathway."""

    detected_emotions: list[dict[str, Any]] = Field(default_factory=list)
    emotional_reaction: str = ""  # How the character feels
    appropriate_response_tone: str = ""
    affect_influence: float = Field(0.5, ge=0.0, le=1.0)  # How much emotion affects response


class FusedState(BaseModel):
    """Result of fusing cognitive and emotional processing."""

    cognitive: CognitiveOutput
    emotional: EmotionalOutput
    fused_emotional_state: EmotionalState
    response_guidance: str = ""  # Guidance for response generation


# ============================================================================
# Hierarchical Memory System
# ============================================================================


class MemoryType(Enum):
    """Types of memory in the hierarchy."""

    WORKING = auto()  # Recent conversation
    EPISODIC = auto()  # Specific events/experiences
    SEMANTIC = auto()  # Facts, concepts, relationships


class MemoryEntry(BaseModel):
    """A single memory entry."""

    id: str
    content: str
    memory_type: MemoryType
    timestamp: datetime
    importance: float = Field(0.5, ge=0.0, le=1.0)

    # For semantic memory
    entities: list[str] = Field(default_factory=list)
    relationships: dict[str, str] = Field(default_factory=dict)

    # Metadata
    source: str = ""  # Where this memory came from
    access_count: int = 0
    last_accessed: datetime | None = None


class WorkingMemory:
    """Working memory - recent conversation context.

    Always kept in context, limited size (3-5 recent exchanges).
    """

    def __init__(self, max_size: int = 5):
        self.max_size = max_size
        self.messages: deque[dict[str, str]] = deque(maxlen=max_size)

    def add(self, role: str, content: str) -> None:
        """Add a message to working memory."""
        self.messages.append({"role": role, "content": content})

    def get_recent(self, n: int | None = None) -> list[dict[str, str]]:
        """Get recent messages."""
        if n is None:
            n = self.max_size
        return list(self.messages)[-n:]

    def clear(self) -> None:
        """Clear working memory."""
        self.messages.clear()


class EpisodicMemory:
    """Episodic memory - specific events and experiences.

    Stored as vector embeddings for semantic retrieval.
    """

    def __init__(self):
        self.episodes: list[MemoryEntry] = []

    async def add(self, entry: MemoryEntry) -> None:
        """Add an episodic memory."""
        self.episodes.append(entry)

    async def retrieve(
        self, query: str, query_embedding: list[float] | None = None, top_k: int = 3
    ) -> list[MemoryEntry]:
        """Retrieve relevant episodes."""
        # Placeholder - actual implementation uses vector similarity
        return sorted(
            self.episodes,
            key=lambda e: e.importance * (0.9 if e.last_accessed else 1.0),
            reverse=True,
        )[:top_k]


class SemanticMemory:
    """Semantic memory - facts, concepts, and relationships.

    Stored as a knowledge graph.
    """

    def __init__(self):
        self.facts: dict[str, str] = {}  # entity -> fact
        self.relationships: dict[str, dict[str, str]] = {}  # entity -> {relation -> target}

    def add_fact(self, entity: str, fact: str) -> None:
        """Add a fact about an entity."""
        self.facts[entity] = fact

    def add_relationship(self, entity1: str, relation: str, entity2: str) -> None:
        """Add a relationship between entities."""
        if entity1 not in self.relationships:
            self.relationships[entity1] = {}
        self.relationships[entity1][relation] = entity2

    def query_entity(self, entity: str) -> dict[str, Any]:
        """Query information about an entity."""
        return {
            "fact": self.facts.get(entity),
            "relationships": self.relationships.get(entity, {}),
        }

    def extract_entities(self, text: str) -> list[str]:
        """Extract entities from text."""
        # Placeholder - actual implementation uses NER
        return []


# ============================================================================
# Consistency Validation
# ============================================================================


class ValidationCheck(BaseModel):
    """Result of a single validation check."""

    check_name: str
    passed: bool
    score: float = Field(0.0, ge=0.0, le=1.0)
    feedback: str = ""


class ValidationResult(BaseModel):
    """Result of consistency validation."""

    checks: list[ValidationCheck] = Field(default_factory=list)
    overall_valid: bool = False
    overall_score: float = Field(0.0, ge=0.0, le=1.0)
    suggested_improvements: list[str] = Field(default_factory=list)


# ============================================================================
# User Modeling
# ============================================================================


class UserPreference(BaseModel):
    """A learned user preference."""

    category: str  # e.g., "topic", "style", "interaction_mode"
    value: str
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    learned_from: str = ""  # Which interaction taught us this
    learned_at: datetime = Field(default_factory=datetime.now)


class UserModel(BaseModel):
    """Model of the user for personalization."""

    user_id: str
    preferences: list[UserPreference] = Field(default_factory=list)
    emotional_triggers: dict[str, float] = Field(default_factory=dict)
    interaction_patterns: list[dict[str, Any]] = Field(default_factory=list)

    # Relationship dynamics
    trust_level: float = Field(0.3, ge=0.0, le=1.0)
    familiarity: float = Field(0.0, ge=0.0, le=1.0)
    preferred_style: str = ""

    # Temporal
    interaction_count: int = 0
    total_messages: int = 0
    first_interaction_at: datetime = Field(default_factory=datetime.now)
    last_interaction_at: datetime | None = None


__all__ = [
    # Core Identity
    "CoreValues",
    "BehavioralMatrix",
    "CoreIdentity",
    # Dynamic Context
    "EmotionalState",
    "RelationshipState",
    "CognitiveState",
    "DynamicContext",
    # Knowledge & Task
    "KnowledgeBoundary",
    "RetrievedKnowledge",
    "TaskContext",
    "KnowledgeContext",
    # Prompt System
    "LayeredPrompt",
    # Cognitive-Emotional
    "CognitiveOutput",
    "EmotionalOutput",
    "FusedState",
    # Memory
    "MemoryType",
    "MemoryEntry",
    "WorkingMemory",
    "EpisodicMemory",
    "SemanticMemory",
    # Validation
    "ValidationCheck",
    "ValidationResult",
    # User Model
    "UserPreference",
    "UserModel",
]
