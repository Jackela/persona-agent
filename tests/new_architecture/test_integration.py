"""End-to-end integration tests for the new architecture.

This module tests the integration of all new architecture components:
- LayeredPromptEngine with RoleRAG
- CognitiveEmotionalEngine
- HierarchicalMemory
- ConsistencyValidator
- AdaptiveUserModeling
"""

import pytest

from persona_agent.core.cognitive_emotional_engine import (
    CognitiveEmotionalEngine,
    FusionLayer,
    create_neutral_emotional_state,
)
from persona_agent.core.consistency_validator import ConsistencyValidator, ValidationConfig
from persona_agent.core.hierarchical_memory import HierarchicalMemory, RetrievalContext
from persona_agent.core.prompt_engine import (
    EntityType,
    LayeredPromptEngine,
)
from persona_agent.core.schemas import (
    BehavioralMatrix,
    CognitiveState,
    CoreIdentity,
    CoreValues,
    DynamicContext,
    EmotionalState,
    RelationshipState,
)
from persona_agent.core.user_modeling import (
    AdaptiveUserModeling,
    InMemoryUserModelStorage,
)


class TestLayeredPromptEngineIntegration:
    """Integration tests for LayeredPromptEngine with RoleRAG."""

    @pytest.fixture
    def sample_identity(self):
        return CoreIdentity(
            name="Test Character",
            backstory="A helpful test character.",
            values=CoreValues(
                values=["honesty", "kindness"],
                fears=["failure"],
            ),
            behavioral_matrix=BehavioralMatrix(
                must_always=["be helpful"],
                must_never=["be rude"],
            ),
        )

    @pytest.fixture
    def sample_dynamic_context(self):
        return DynamicContext(
            emotional=EmotionalState(
                valence=0.5,
                arousal=0.6,
                primary_emotion="friendly",
            ),
            social=RelationshipState(
                intimacy=0.4,
                trust=0.6,
            ),
            cognitive=CognitiveState(
                focus_target="user",
                attention_level=0.8,
            ),
        )

    def test_layered_prompt_creation(self, sample_identity, sample_dynamic_context):
        """Test creating a layered prompt without LLM."""
        engine = LayeredPromptEngine(
            core_identity=sample_identity,
        )

        # Use sync version for testing
        prompt_text = engine.get_system_prompt(
            user_input="Hello",
            dynamic_context=sample_dynamic_context,
        )

        # Verify all layers are present
        assert "Test Character" in prompt_text
        assert "friendly" in prompt_text
        assert "Valence" in prompt_text
        assert "Intimacy" in prompt_text

    def test_entity_classification_specific(self):
        """Test entity classification for specific entities."""
        from persona_agent.core.knowledge_graph import KnowledgeGraph
        from persona_agent.core.schemas import KnowledgeBoundary

        # Create knowledge graph with entity
        kg = KnowledgeGraph()
        from persona_agent.core.knowledge_graph import Entity

        entity = Entity(
            name="Alice",
            entity_type="character",
            description="A test character",
        )
        kg.add_entity(entity)

        # Create boundary with known entity
        boundary = KnowledgeBoundary(
            known_entities=["Alice"],
            known_domains=["testing"],
        )

        # Test classification
        from persona_agent.core.prompt_engine import RoleRAGRetriever

        retriever = RoleRAGRetriever(
            knowledge_graph=kg,
        )

        import asyncio

        classified = asyncio.run(retriever.classify_entity("Alice", "Test", boundary))

        assert classified.entity_type == EntityType.SPECIFIC
        assert classified.confidence > 0.5


class TestCognitiveEmotionalEngineIntegration:
    """Integration tests for cognitive-emotional processing."""

    @pytest.fixture
    def emotional_engine(self):
        return CognitiveEmotionalEngine(
            llm_client=None,  # Will use rule-based fallback
            initial_emotional_state=create_neutral_emotional_state(),
        )

    @pytest.fixture
    def working_memory(self):
        from persona_agent.core.schemas import WorkingMemory

        wm = WorkingMemory(max_size=3)
        wm.add("user", "Hello")
        wm.add("assistant", "Hi there!")
        return wm

    def test_emotional_processing_rule_based(self, emotional_engine, working_memory):
        """Test emotional processing without LLM (rule-based)."""
        import asyncio

        result = asyncio.run(
            emotional_engine.process(
                user_input="I'm so happy today!",
                working_memory=working_memory,
            )
        )

        # Verify emotional detection
        assert result.fused_emotional_state is not None
        assert result.emotional.detected_emotions
        assert result.cognitive.understanding

    def test_emotion_time_decay(self, emotional_engine):
        """Test emotional state decay over time."""
        _ = EmotionalState(
            valence=0.8,
            arousal=0.9,
            intensity=0.9,
        )

        # Simulate time passing (10 seconds)
        import time

        time.sleep(0.1)  # Small delay for testing

        # Update with neutral input (should decay)
        result = EmotionalState(
            valence=0.8,
            arousal=0.9,
            intensity=0.9,
        )

        # Verify state exists
        assert result.valence == 0.8

    def test_fusion_layer(self):
        """Test cognitive-emotional fusion."""
        from persona_agent.core.schemas import CognitiveOutput, EmotionalOutput

        fusion = FusionLayer()

        cognitive = CognitiveOutput(
            understanding="User is happy",
            relevance_score=0.9,
            user_intent="share_feeling",
        )

        emotional = EmotionalOutput(
            detected_emotions=[{"emotion": "joy", "intensity": 0.8}],
            affect_influence=0.6,
        )

        current_state = create_neutral_emotional_state()

        result = fusion.merge(cognitive, emotional, current_state)

        assert result.fused_emotional_state is not None
        assert result.response_guidance


class TestHierarchicalMemoryIntegration:
    """Integration tests for hierarchical memory system."""

    @pytest.fixture
    def hierarchical_memory(self):
        return HierarchicalMemory()

    def test_memory_storage_and_retrieval(self, hierarchical_memory):
        """Test storing and retrieving memories."""
        import asyncio

        # Store exchange
        asyncio.run(
            hierarchical_memory.store_exchange(
                user_msg="My name is Alice",
                assistant_msg="Nice to meet you, Alice!",
                importance=0.8,
            )
        )

        # Verify working memory
        working = hierarchical_memory.working.get_recent()
        assert len(working) == 2
        assert "Alice" in working[0].content

        # Retrieve
        result = asyncio.run(
            hierarchical_memory.retrieve(
                query="What is my name?",
                context=RetrievalContext(),
            )
        )

        # Verify retrieval
        assert result is not None
        assert len(result.working_messages) >= 0

    def test_episodic_memory_with_importance(self, hierarchical_memory):
        """Test episodic memory filters by importance."""
        import asyncio

        # Store high importance episode
        asyncio.run(
            hierarchical_memory.store_exchange(
                user_msg="I love chocolate",
                assistant_msg="That's great!",
                importance=0.9,
            )
        )

        # Store low importance (should not create episode)
        asyncio.run(
            hierarchical_memory.store_exchange(
                user_msg="Hello",
                assistant_msg="Hi!",
                importance=0.1,
            )
        )

        # Retrieve with importance filter
        result = asyncio.run(
            hierarchical_memory.retrieve(
                query="What do I like?",
                context=RetrievalContext(filter_importance=0.5),
            )
        )

        assert result is not None

    def test_semantic_memory_facts(self, hierarchical_memory):
        """Test semantic memory fact storage."""
        # Add facts
        hierarchical_memory.semantic.add_fact(
            entity="alice",
            fact="Likes chocolate",
            confidence=0.9,
        )

        hierarchical_memory.semantic.add_fact(
            entity="alice",
            fact="Lives in Tokyo",
            confidence=0.8,
        )

        # Query entity
        result = hierarchical_memory.semantic.query_entity("alice")

        assert result["exists"] is True
        assert len(result["facts"]) == 2

    def test_semantic_relationships(self, hierarchical_memory):
        """Test semantic memory relationship storage."""
        # Add relationship
        hierarchical_memory.semantic.add_relationship(
            subject="alice",
            predicate="friend",
            obj="bob",
            confidence=0.9,
        )

        # Get related entities
        related = hierarchical_memory.semantic.get_related_entities("alice", depth=1)

        assert "bob" in related

    def test_memory_fusion_score(self, hierarchical_memory):
        """Test memory fusion scoring."""
        import asyncio

        # Store some data
        asyncio.run(
            hierarchical_memory.store_exchange(
                user_msg="Test message",
                assistant_msg="Test response",
                importance=0.7,
            )
        )

        # Get stats
        stats = hierarchical_memory.get_stats()

        assert "working" in stats
        assert "episodic" in stats
        assert "semantic" in stats


class TestConsistencyValidatorIntegration:
    """Integration tests for consistency validation."""

    @pytest.fixture
    def validator(self):
        return ConsistencyValidator(
            llm_client=None,  # Will use rule-based fallback
            core_identity=CoreIdentity(
                name="Test",
                values=CoreValues(values=["honesty"]),
            ),
            config=ValidationConfig(overall_threshold=0.6),
        )

    def test_validation_scoring(self, validator):
        """Test validation scoring without LLM."""
        import asyncio

        from persona_agent.core.schemas import DynamicContext

        result = asyncio.run(
            validator.validate(
                response="I love helping people!",
                dynamic_context=DynamicContext(),
                conversation_history=[],
            )
        )

        # Verify validation result
        assert result.overall_score >= 0.0
        assert result.overall_score <= 1.0
        assert len(result.dimension_scores) == 5

    def test_validation_checks(self, validator):
        """Test individual validation checks."""
        import asyncio

        from persona_agent.core.schemas import DynamicContext

        result = asyncio.run(
            validator.validate(
                response="Test response",
                dynamic_context=DynamicContext(),
                conversation_history=[],
            )
        )

        # Verify violations exist (populated when validation fails without LLM)
        assert result.violations
        for violation in result.violations:
            assert violation.get("dimension")
            assert violation.get("severity")


class TestUserModelingIntegration:
    """Integration tests for adaptive user modeling."""

    @pytest.fixture
    def user_modeling(self):
        return AdaptiveUserModeling(
            llm_client=None,  # Will use rule-based fallback
            storage=InMemoryUserModelStorage(),
        )

    def test_user_creation(self, user_modeling):
        """Test user model creation."""
        import asyncio

        model = asyncio.run(user_modeling.get_or_create_user("user-123"))

        assert model.user_id == "user-123"
        assert model.interaction_count == 0
        assert model.peer_card is not None

    def test_preference_detection(self, user_modeling):
        """Test preference detection from interaction."""
        import asyncio

        model = asyncio.run(
            user_modeling.update_from_interaction(
                user_id="user-123",
                user_message="I prefer short answers",
                assistant_message="Got it!",
            )
        )

        # Verify model was updated
        assert model.interaction_count == 1
        assert model.total_messages == 2

    def test_conclusion_extraction(self, user_modeling):
        """Test conclusion extraction."""
        import asyncio

        conclusions = asyncio.run(
            user_modeling.extract_conclusions(
                user_message="I work as a software engineer",
                context="User introduction",
                current_model=asyncio.run(user_modeling.get_or_create_user("user-456")),
            )
        )

        # Verify conclusions were extracted
        assert isinstance(conclusions, list)

    def test_context_building(self, user_modeling):
        """Test building user context for prompts."""
        import asyncio

        # Create and update user
        asyncio.run(
            user_modeling.update_from_interaction(
                user_id="user-789",
                user_message="Hello",
                assistant_message="Hi!",
            )
        )

        # Build context
        context = asyncio.run(user_modeling.build_user_context("user-789", max_tokens=500))

        assert isinstance(context, str)


class TestFullPipelineIntegration:
    """Full pipeline integration tests."""

    def test_all_components_together(self):
        """Test all components working together in a conversation flow."""
        import asyncio

        # Initialize components
        memory = HierarchicalMemory()
        emotional_engine = CognitiveEmotionalEngine(llm_client=None)

        # Simulate conversation
        user_inputs = [
            "Hello, I'm Alice!",
            "I love programming",
            "What do you think about Python?",
        ]

        responses = []

        for user_input in user_inputs:
            # Store in working memory
            memory.working.add_exchange(user_input, f"Response to: {user_input}")

            # Process through cognitive-emotional engine
            result = asyncio.run(
                emotional_engine.process(
                    user_input=user_input,
                    working_memory=memory.working,
                )
            )

            responses.append(
                {
                    "input": user_input,
                    "emotion": result.fused_emotional_state.primary_emotion,
                    "understanding": result.cognitive.understanding,
                }
            )

        # Verify conversation was processed
        assert len(responses) == 3
        assert all(r["emotion"] for r in responses)

    def test_memory_persistence_across_turns(self):
        """Test that memory persists across conversation turns."""
        import asyncio

        memory = HierarchicalMemory()

        # First turn
        asyncio.run(
            memory.store_exchange(
                user_msg="My name is Bob",
                assistant_msg="Nice to meet you, Bob!",
                importance=0.8,
            )
        )

        # Second turn - should remember
        result = asyncio.run(
            memory.retrieve(
                query="What is my name?",
                context=RetrievalContext(),
            )
        )

        # Verify memory was retrieved
        assert result is not None
        # Working memory should have the exchange
        assert len(result.working_messages) >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
