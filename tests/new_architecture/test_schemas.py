"""Tests for LayeredPromptEngine and RoleRAG integration."""

import pytest

from persona_agent.core.knowledge_graph import Entity, KnowledgeGraph, Relation
from persona_agent.core.schemas import (
    BehavioralMatrix,
    CognitiveState,
    CoreIdentity,
    CoreValues,
    DynamicContext,
    EmotionalState,
    KnowledgeBoundary,
    KnowledgeContext,
    LayeredPrompt,
    RelationshipState,
    TaskContext,
)


class TestCoreIdentity:
    """Tests for CoreIdentity schema."""

    def test_core_identity_creation(self):
        """Test creating a core identity."""
        identity = CoreIdentity(
            name="Test Character",
            version="1.0.0",
            backstory="A test character for testing.",
            values=CoreValues(
                values=["honesty", "kindness"],
                fears=["failure"],
                desires=["success"],
            ),
            behavioral_matrix=BehavioralMatrix(
                must_always=["be helpful"],
                must_never=["be rude"],
            ),
        )

        assert identity.name == "Test Character"
        assert identity.version == "1.0.0"
        assert "honesty" in identity.values.values


class TestEmotionalState:
    """Tests for EmotionalState schema with valence-arousal model."""

    def test_emotional_state_defaults(self):
        """Test emotional state with default values."""
        state = EmotionalState()

        assert state.valence == 0.0
        assert state.arousal == 0.5
        assert state.dominance == 0.5
        assert state.primary_emotion == "neutral"

    def test_emotional_state_custom(self):
        """Test emotional state with custom values."""
        state = EmotionalState(
            valence=0.8,
            arousal=0.7,
            dominance=0.6,
            primary_emotion="happy",
            intensity=0.9,
        )

        assert state.valence == 0.8
        assert state.arousal == 0.7
        assert state.primary_emotion == "happy"

    def test_emotional_state_validation(self):
        """Test emotional state value validation."""
        # Should raise validation error for out-of-range values
        with pytest.raises(ValueError):
            EmotionalState(valence=2.0)  # Max is 1.0

        with pytest.raises(ValueError):
            EmotionalState(arousal=-0.1)  # Min is 0.0


class TestDynamicContext:
    """Tests for DynamicContext schema."""

    def test_dynamic_context_creation(self):
        """Test creating dynamic context."""
        context = DynamicContext(
            emotional=EmotionalState(
                valence=0.5,
                arousal=0.6,
                primary_emotion="curious",
            ),
            social=RelationshipState(
                intimacy=0.4,
                trust=0.6,
                current_stage="getting_to_know",
            ),
            cognitive=CognitiveState(
                focus_target="user",
                attention_level=0.9,
                current_intention="help",
            ),
            conversation_turn=5,
            topic="testing",
        )

        assert context.emotional.primary_emotion == "curious"
        assert context.social.trust == 0.6
        assert context.cognitive.focus_target == "user"


class TestLayeredPrompt:
    """Tests for LayeredPrompt schema and conversion."""

    @pytest.fixture
    def sample_identity(self):
        return CoreIdentity(
            name="TestBot",
            backstory="A helpful test bot.",
            values=CoreValues(values=["helpfulness"]),
        )

    @pytest.fixture
    def sample_dynamic_context(self):
        return DynamicContext(
            emotional=EmotionalState(primary_emotion="friendly"),
            social=RelationshipState(intimacy=0.5),
            cognitive=CognitiveState(),
        )

    @pytest.fixture
    def sample_knowledge_context(self):
        return KnowledgeContext(
            boundaries=KnowledgeBoundary(
                known_domains=["testing", "python"],
                known_entities=["pytest", "unittest"],
            ),
            task=TaskContext(
                task_type="testing",
                instructions="Run tests",
            ),
        )

    def test_layered_prompt_creation(
        self, sample_identity, sample_dynamic_context, sample_knowledge_context
    ):
        """Test creating a layered prompt."""
        prompt = LayeredPrompt(
            core_identity=sample_identity,
            dynamic_context=sample_dynamic_context,
            knowledge_context=sample_knowledge_context,
        )

        assert prompt.core_identity.name == "TestBot"
        assert prompt.dynamic_context.emotional.primary_emotion == "friendly"
        assert "testing" in prompt.knowledge_context.boundaries.known_domains

    def test_to_system_prompt(
        self, sample_identity, sample_dynamic_context, sample_knowledge_context
    ):
        """Test converting layered prompt to system prompt string."""
        prompt = LayeredPrompt(
            core_identity=sample_identity,
            dynamic_context=sample_dynamic_context,
            knowledge_context=sample_knowledge_context,
        )

        system_prompt = prompt.to_system_prompt()

        # Check all layers are included
        assert "TestBot" in system_prompt
        assert "friendly" in system_prompt
        assert "testing" in system_prompt
        assert "Valence" in system_prompt  # Emotional state
        assert "Intimacy" in system_prompt  # Relationship state


class TestKnowledgeGraph:
    """Tests for KnowledgeGraph implementation."""

    @pytest.fixture
    def sample_graph(self):
        """Create a sample knowledge graph."""
        graph = KnowledgeGraph()

        # Add entities
        alice = Entity(
            name="Alice",
            entity_type="character",
            description="A test character",
        )
        bob = Entity(
            name="Bob",
            entity_type="character",
            description="Another test character",
        )

        graph.add_entity(alice)
        graph.add_entity(bob)

        # Add relation
        relation = Relation(
            source="Alice",
            target="Bob",
            relation_type="friend",
            description="Alice and Bob are friends",
            strength=0.8,
        )
        graph.add_relation(relation)

        return graph

    def test_add_entity(self):
        """Test adding entities to graph."""
        graph = KnowledgeGraph()
        entity = Entity(name="Test", entity_type="character")

        graph.add_entity(entity)

        assert "Test" in graph.entities
        assert graph.graph.has_node("Test")

    def test_add_relation(self, sample_graph):
        """Test adding relations between entities."""
        relations = sample_graph.get_relations("Alice")

        assert len(relations) == 1
        assert relations[0].relation_type == "friend"
        assert relations[0].target == "Bob"

    def test_get_neighbors(self, sample_graph):
        """Test getting neighbor entities."""
        neighbors = sample_graph.get_1hop_neighbors("Alice")

        assert len(neighbors) == 1
        assert neighbors[0].name == "Bob"

    def test_entity_lookup_by_alias(self):
        """Test looking up entities by alias."""
        graph = KnowledgeGraph()
        entity = Entity(
            name="Anakin Skywalker",
            original_names=["Darth Vader", "Lord Vader"],
            entity_type="character",
        )
        graph.add_entity(entity)

        # Lookup by canonical name
        found = graph.get_entity("Anakin Skywalker")
        assert found is not None

        # Lookup by alias
        found_by_alias = graph.get_entity("Darth Vader")
        assert found_by_alias is not None
        assert found_by_alias.name == "Anakin Skywalker"

    def test_merge_entities(self):
        """Test entity normalization by merging aliases."""
        graph = KnowledgeGraph()

        # Create entities with aliases
        anakin = Entity(name="Anakin Skywalker", entity_type="character")
        vader = Entity(
            name="Darth Vader",
            original_names=["Lord Vader"],
            entity_type="character",
        )

        graph.add_entity(anakin)
        graph.add_entity(vader)

        # Add Luke Skywalker entity (needed for relation)
        luke = Entity(name="Luke Skywalker", entity_type="character")
        graph.add_entity(luke)

        # Add a relation to the alias
        graph.add_entity(vader)

        # Add a relation to the alias
        graph.add_relation(
            Relation(
                source="Darth Vader",
                target="Luke Skywalker",
                relation_type="parent",
            )
        )

        # Merge
        graph.merge_entities("Anakin Skywalker", ["Darth Vader"])

        # Check merge
        assert "Darth Vader" not in graph.entities
        assert "Lord Vader" in graph.entities["Anakin Skywalker"].original_names

        # Check relation was redirected
        relations = graph.get_relations("Anakin Skywalker")
        assert any(r.target == "Luke Skywalker" for r in relations)

    def test_to_context_text(self, sample_graph):
        """Test converting graph to context text."""
        text = sample_graph.to_context_text()

        assert "Alice" in text
        assert "Bob" in text
        assert "friends" in text

    def test_statistics(self, sample_graph):
        """Test graph statistics."""
        stats = sample_graph.statistics()

        assert stats["num_entities"] == 2
        assert stats["num_relations"] == 1
        assert stats["num_nodes"] == 2
        assert stats["num_edges"] == 1


class TestKnowledgeBoundary:
    """Tests for KnowledgeBoundary (RoleRAG integration)."""

    def test_boundary_creation(self):
        """Test creating knowledge boundaries."""
        boundary = KnowledgeBoundary(
            known_domains=["python", "testing"],
            known_entities=["pytest"],
            unknown_domains=["javascript", "ruby"],
            confidence=0.9,
        )

        assert "python" in boundary.known_domains
        assert "javascript" in boundary.unknown_domains
        assert boundary.confidence == 0.9

    def test_is_within_boundary(self):
        """Test checking if query is within knowledge boundary."""
        boundary = KnowledgeBoundary(
            known_domains=["python"],
            known_entities=["pytest"],
        )

        # Check known domain
        assert "python" in boundary.known_domains

        # Check unknown domain
        assert "javascript" not in boundary.known_domains
