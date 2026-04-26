"""Comprehensive unit tests for user_modeling.py.

Covers all public methods and edge cases for:
- Conclusion
- UserPeerCard
- UserPreference
- UserModel
- InMemoryUserModelStorage
- AdaptiveUserModeling
"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from persona_agent.core.user_modeling import (
    AdaptiveUserModeling,
    Conclusion,
    InMemoryUserModelStorage,
    UserModel,
    UserModelStorage,
    UserPeerCard,
    UserPreference,
)


class TestConclusion:
    """Tests for Conclusion dataclass."""

    def test_basic_creation(self):
        """Test basic Conclusion creation."""
        c = Conclusion(
            conclusion_type="deductive",
            premises=["User says they are vegan"],
            conclusion="User follows a plant-based diet",
            confidence=0.8,
        )

        assert c.conclusion_type == "deductive"
        assert c.premises == ["User says they are vegan"]
        assert c.conclusion == "User follows a plant-based diet"
        assert c.confidence == 0.8
        assert isinstance(c.created_at, datetime)
        assert c.source_interaction == ""

    def test_to_prompt_context(self):
        """Test formatting for prompt inclusion."""
        c = Conclusion(
            conclusion_type="inductive",
            conclusion="User enjoys hiking",
            confidence=0.75,
        )

        result = c.to_prompt_context()
        assert result == "[INDUCTIVE] User enjoys hiking (confidence: 0.75)"

    @pytest.mark.parametrize("c_type", ["deductive", "inductive", "abductive"])
    def test_all_types(self, c_type):
        """Test all conclusion types produce valid output."""
        c = Conclusion(conclusion_type=c_type, conclusion="Test", confidence=0.5)
        result = c.to_prompt_context()
        assert c_type.upper() in result
        assert "Test" in result

    def test_default_values(self):
        """Test default field values."""
        c = Conclusion(conclusion_type="deductive", conclusion="Test")

        assert c.premises == []
        assert c.confidence == 0.5
        assert c.source_interaction == ""


class TestUserPeerCard:
    """Tests for UserPeerCard biographical cache."""

    def test_basic_creation(self):
        """Test basic creation with defaults."""
        card = UserPeerCard()
        assert card.facts == []
        assert card.access_timestamps == []

    def test_add_fact_new(self):
        """Test adding a new fact."""
        card = UserPeerCard()
        card.add_fact("User is a software engineer")

        assert len(card.facts) == 1
        assert card.facts[0] == "User is a software engineer"
        assert len(card.access_timestamps) == 1

    def test_add_fact_duplicate_moves_to_end(self):
        """Test duplicate fact moves to end (LRU)."""
        card = UserPeerCard()
        card.add_fact("Fact A")
        card.add_fact("Fact B")
        card.add_fact("Fact A")

        assert card.facts == ["Fact B", "Fact A"]
        assert len(card.access_timestamps) == 2

    def test_add_fact_empty_ignored(self):
        """Test empty/whitespace facts are ignored."""
        card = UserPeerCard()
        card.add_fact("")
        card.add_fact("   ")

        assert card.facts == []

    def test_add_fact_eviction_at_40(self):
        """Test LRU eviction when max capacity reached."""
        card = UserPeerCard()

        for i in range(40):
            card.add_fact(f"Fact {i}")

        assert len(card.facts) == 40
        assert card.facts[0] == "Fact 0"

        card.add_fact("Fact 40")
        assert len(card.facts) == 40
        assert card.facts[0] == "Fact 1"
        assert card.facts[-1] == "Fact 40"

    def test_access_fact_exists(self):
        """Test accessing an existing fact updates timestamp."""
        card = UserPeerCard()
        card.add_fact("Fact A")
        card.add_fact("Fact B")

        old_ts = card.access_timestamps[0]
        result = card.access_fact("Fact A")

        assert result is True
        assert card.access_timestamps[0] >= old_ts

    def test_access_fact_not_exists(self):
        """Test accessing non-existent fact returns False."""
        card = UserPeerCard()
        card.add_fact("Fact A")

        result = card.access_fact("Fact B")
        assert result is False

    def test_get_facts_no_filter(self):
        """Test getting all facts without filter."""
        card = UserPeerCard()
        card.add_fact("[work] Engineer")
        card.add_fact("[hobby] Hiking")

        facts = card.get_facts()
        assert len(facts) == 2
        assert facts[0] == "[work] Engineer"

    def test_get_facts_with_category(self):
        """Test filtering facts by category prefix."""
        card = UserPeerCard()
        card.add_fact("[work] Engineer")
        card.add_fact("[hobby] Hiking")
        card.add_fact("[work] Manager")

        work_facts = card.get_facts(category="work")
        assert len(work_facts) == 2
        assert all(f.startswith("[work]") for f in work_facts)

    def test_merge_facts(self):
        """Test merging multiple facts."""
        card = UserPeerCard()
        card.merge_facts(["Engineer", "Likes coffee"], source="work")

        assert len(card.facts) == 2
        assert card.facts[0] == "[work] Engineer"
        assert card.facts[1] == "[work] Likes coffee"

    def test_merge_facts_no_source(self):
        """Test merging facts without source prefix."""
        card = UserPeerCard()
        card.merge_facts(["Fact 1", "Fact 2"])

        assert card.facts == ["Fact 1", "Fact 2"]

    def test_validate_max_facts(self):
        """Test validator truncates facts over 40."""
        facts = [f"Fact {i}" for i in range(45)]
        card = UserPeerCard(facts=facts)

        assert len(card.facts) == 40
        assert card.facts[0] == "Fact 5"


class TestUserPreference:
    """Tests for UserPreference with confidence tracking."""

    def test_basic_creation(self):
        """Test basic preference creation."""
        p = UserPreference(category="communication", value="direct", confidence=0.7)

        assert p.category == "communication"
        assert p.value == "direct"
        assert p.confidence == 0.7
        assert p.evidence_count == 1

    def test_reinforce_logarithmic_growth(self):
        """Test confidence increases with logarithmic growth."""
        p = UserPreference(category="topic", value="AI", confidence=0.5)

        initial_conf = p.confidence
        p.reinforce()

        assert p.evidence_count == 2
        assert p.confidence > initial_conf
        assert p.confidence < 1.0

    def test_reinforce_multiple_times(self):
        """Test multiple reinforcements approach but don't reach 1.0."""
        p = UserPreference(category="style", value="formal", confidence=0.5)

        for _ in range(20):
            p.reinforce()

        assert p.confidence > 0.9
        assert p.confidence < 1.0
        assert p.evidence_count == 21

    def test_reinforce_with_source(self):
        """Test reinforce updates learned_from."""
        p = UserPreference(category="tone", value="friendly")
        p.reinforce(source="interaction_123")

        assert p.learned_from == "interaction_123"

    def test_contradict_aggressive_drop(self):
        """Test contradiction drops confidence aggressively."""
        p = UserPreference(category="topic", value="sports", confidence=0.8)
        p.evidence_count = 5

        p.contradict()

        assert p.confidence < 0.8
        assert p.evidence_count == 4

    def test_contradict_minimum_confidence(self):
        """Test confidence doesn't drop below 0.1."""
        p = UserPreference(category="topic", value="test", confidence=0.1)

        p.contradict()

        assert p.confidence == 0.1
        assert p.evidence_count == 1

    def test_to_prompt_context(self):
        """Test formatting for prompt inclusion."""
        p = UserPreference(category="communication", value="brief", confidence=0.75)

        result = p.to_prompt_context()
        assert result == "- communication: brief (confidence: 75%)"


class TestUserModel:
    """Tests for UserModel complete user representation."""

    def test_basic_creation(self):
        """Test basic user model creation."""
        model = UserModel(user_id="user123")

        assert model.user_id == "user123"
        assert model.trust_level == 0.3
        assert model.familiarity == 0.0
        assert model.interaction_count == 0
        assert model.total_messages == 0
        assert model.version == "1.0.0"

    def test_add_conclusion(self):
        """Test adding a conclusion."""
        model = UserModel(user_id="user1")
        c = Conclusion(
            conclusion_type="deductive",
            conclusion="User likes Python",
            confidence=0.8,
        )

        model.add_conclusion(c)

        assert len(model.conclusions) == 1
        assert model.conclusions[0].conclusion == "User likes Python"

    def test_add_conclusion_high_confidence_to_peer_card(self):
        """Test high-confidence conclusions are added to peer card."""
        model = UserModel(user_id="user1")
        c = Conclusion(
            conclusion_type="inductive",
            conclusion="User is a developer",
            confidence=0.7,
        )

        model.add_conclusion(c)

        assert len(model.peer_card.facts) == 1
        assert "[conclusion] User is a developer" in model.peer_card.facts

    def test_add_conclusion_low_confidence_not_in_peer_card(self):
        """Test low-confidence conclusions don't go to peer card."""
        model = UserModel(user_id="user1")
        c = Conclusion(
            conclusion_type="abductive",
            conclusion="User might be tired",
            confidence=0.5,
        )

        model.add_conclusion(c)

        assert len(model.peer_card.facts) == 0

    def test_add_preference_new(self):
        """Test adding a new preference."""
        model = UserModel(user_id="user1")
        p = UserPreference(category="communication", value="direct", confidence=0.7)

        model.add_preference(p)

        key = "communication:direct"
        assert key in model.preferences
        assert model.preferences[key].value == "direct"

    def test_add_preference_reinforces_existing(self):
        """Test adding duplicate preference reinforces existing."""
        model = UserModel(user_id="user1")
        p1 = UserPreference(category="topic", value="AI", confidence=0.6)
        p2 = UserPreference(category="topic", value="AI", confidence=0.6)

        model.add_preference(p1)
        initial_conf = model.preferences["topic:AI"].confidence

        model.add_preference(p2)

        assert model.preferences["topic:AI"].confidence > initial_conf
        assert model.preferences["topic:AI"].evidence_count == 2

    def test_get_preferences_by_category(self):
        """Test filtering preferences by category."""
        model = UserModel(user_id="user1")
        model.add_preference(UserPreference(category="communication", value="direct"))
        model.add_preference(UserPreference(category="communication", value="brief"))
        model.add_preference(UserPreference(category="topic", value="AI"))

        comm_prefs = model.get_preferences_by_category("communication")
        assert len(comm_prefs) == 2
        assert all(p.category == "communication" for p in comm_prefs)

    def test_get_preferences_by_category_empty(self):
        """Test empty result for non-existent category."""
        model = UserModel(user_id="user1")
        result = model.get_preferences_by_category("nonexistent")
        assert result == []

    def test_update_emotional_trigger_new(self):
        """Test adding new emotional trigger."""
        model = UserModel(user_id="user1")
        model.update_emotional_trigger("work stress", 0.8)

        assert model.emotional_triggers["work stress"] == 0.24

    def test_update_emotional_trigger_existing(self):
        """Test updating existing trigger with EMA."""
        model = UserModel(user_id="user1")
        model.update_emotional_trigger("deadlines", 0.8)
        first_value = model.emotional_triggers["deadlines"]

        model.update_emotional_trigger("deadlines", 0.4)

        assert model.emotional_triggers["deadlines"] == 0.288
        assert model.emotional_triggers["deadlines"] > first_value

    def test_record_interaction(self):
        """Test recording interaction pattern."""
        model = UserModel(user_id="user1")
        pattern = {"sentiment": 0.5, "topic": "AI"}

        model.record_interaction(pattern)

        assert model.interaction_count == 1
        assert model.total_messages == 2
        assert model.last_interaction_at is not None
        assert len(model.interaction_patterns) == 1
        assert "timestamp" in model.interaction_patterns[0]

    def test_record_interaction_rolling_window(self):
        """Test rolling window of 100 patterns."""
        model = UserModel(user_id="user1")

        for i in range(105):
            model.record_interaction({"index": i})

        assert len(model.interaction_patterns) == 100
        assert model.interaction_patterns[0]["index"] == 5
        assert model.interaction_patterns[-1]["index"] == 104

    def test_get_recent_patterns(self):
        """Test retrieving recent patterns."""
        model = UserModel(user_id="user1")

        for i in range(10):
            model.record_interaction({"index": i})

        recent = model.get_recent_patterns(n=3)
        assert len(recent) == 3
        assert recent[0]["index"] == 7
        assert recent[-1]["index"] == 9

    def test_to_dict(self):
        """Test serialization to dict."""
        model = UserModel(user_id="user1")
        model.add_preference(UserPreference(category="topic", value="AI"))

        data = model.to_dict()

        assert data["user_id"] == "user1"
        assert "preferences" in data
        assert "peer_card" in data

    def test_from_dict(self):
        """Test deserialization from dict."""
        model = UserModel(user_id="user1")
        model.add_preference(UserPreference(category="topic", value="AI"))

        data = model.to_dict()
        restored = UserModel.from_dict(data)

        assert restored.user_id == "user1"
        assert len(restored.preferences) == 1
        assert restored.preferences["topic:AI"].value == "AI"

    def test_trust_level_boundary(self):
        """Test trust level boundary constraints."""
        model = UserModel(user_id="user1")

        assert model.trust_level == 0.3

        model.trust_level = 0.5
        assert model.trust_level == 0.5

    def test_familiarity_boundary(self):
        """Test familiarity boundary constraints."""
        model = UserModel(user_id="user1")

        assert model.familiarity == 0.0

        model.familiarity = 0.8
        assert model.familiarity == 0.8


class TestInMemoryUserModelStorage:
    """Tests for InMemoryUserModelStorage CRUD operations."""

    @pytest.fixture
    def storage(self):
        """Create fresh storage instance."""
        return InMemoryUserModelStorage()

    @pytest.fixture
    def sample_model(self):
        """Create a sample user model."""
        return UserModel(user_id="user123")

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, storage):
        """Test getting non-existent user returns None."""
        result = await storage.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_save_and_get(self, storage, sample_model):
        """Test saving and retrieving a model."""
        await storage.save(sample_model)

        result = await storage.get("user123")
        assert result is not None
        assert result.user_id == "user123"

    @pytest.mark.asyncio
    async def test_save_updates_existing(self, storage, sample_model):
        """Test saving updates existing model."""
        await storage.save(sample_model)

        sample_model.trust_level = 0.8
        await storage.save(sample_model)

        result = await storage.get("user123")
        assert result.trust_level == 0.8

    @pytest.mark.asyncio
    async def test_delete_existing(self, storage, sample_model):
        """Test deleting existing model."""
        await storage.save(sample_model)
        await storage.delete("user123")

        result = await storage.get("user123")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, storage):
        """Test deleting non-existent user doesn't raise."""
        await storage.delete("nonexistent")

    @pytest.mark.asyncio
    async def test_list_users_empty(self, storage):
        """Test listing empty storage."""
        users = await storage.list_users()
        assert users == []

    @pytest.mark.asyncio
    async def test_list_users(self, storage):
        """Test listing users."""
        for i in range(5):
            await storage.save(UserModel(user_id=f"user{i}"))

        users = await storage.list_users()
        assert len(users) == 5
        assert "user0" in users
        assert "user4" in users

    @pytest.mark.asyncio
    async def test_list_users_pagination(self, storage):
        """Test pagination with limit and offset."""
        for i in range(10):
            await storage.save(UserModel(user_id=f"user{i}"))

        page1 = await storage.list_users(limit=3, offset=0)
        assert len(page1) == 3

        page2 = await storage.list_users(limit=3, offset=3)
        assert len(page2) == 3

        assert not set(page1) & set(page2)

    @pytest.mark.asyncio
    async def test_list_users_offset_beyond_end(self, storage):
        """Test offset beyond total count returns empty."""
        await storage.save(UserModel(user_id="user1"))

        users = await storage.list_users(offset=10)
        assert users == []


class TestAdaptiveUserModeling:
    """Tests for AdaptiveUserModeling system."""

    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client."""
        client = AsyncMock()
        return client

    @pytest.fixture
    def modeling(self, mock_llm_client):
        """Create AdaptiveUserModeling with mock LLM."""
        return AdaptiveUserModeling(llm_client=mock_llm_client)

    @pytest.fixture
    def mock_conclusions_response(self):
        """Mock response for conclusion extraction."""
        response = MagicMock()
        response.content = json.dumps(
            {
                "conclusions": [
                    {
                        "type": "deductive",
                        "premises": ["User says they are vegan"],
                        "conclusion": "User follows plant-based diet",
                        "confidence": 0.8,
                    },
                    {
                        "type": "inductive",
                        "premises": ["User went hiking twice"],
                        "conclusion": "User enjoys hiking regularly",
                        "confidence": 0.7,
                    },
                ]
            }
        )
        return response

    @pytest.fixture
    def mock_preferences_response(self):
        """Mock response for preference detection."""
        response = MagicMock()
        response.content = json.dumps(
            {
                "preferences": [
                    {
                        "category": "communication",
                        "value": "direct",
                        "confidence": 0.8,
                        "evidence": "User asks straight questions",
                    },
                    {
                        "category": "topic",
                        "value": "AI",
                        "confidence": 0.9,
                        "evidence": "User discusses AI frequently",
                    },
                ]
            }
        )
        return response

    @pytest.fixture
    def mock_triggers_response(self):
        """Mock response for emotional trigger detection."""
        response = MagicMock()
        response.content = json.dumps(
            {
                "triggers": [
                    {"topic": "work deadlines", "intensity": 0.8, "sentiment": "negative"},
                    {"topic": "family", "intensity": 0.9, "sentiment": "positive"},
                ]
            }
        )
        return response

    @pytest.fixture
    def mock_sentiment_response(self):
        """Mock response for sentiment analysis."""
        response = MagicMock()
        response.content = "0.6"
        return response

    @pytest.mark.asyncio
    async def test_get_or_create_user_new(self, modeling):
        """Test creating new user."""
        model = await modeling.get_or_create_user("new_user")

        assert model.user_id == "new_user"
        assert model.trust_level == 0.3

    @pytest.mark.asyncio
    async def test_get_or_create_user_existing(self, modeling):
        """Test retrieving existing user."""
        model1 = await modeling.get_or_create_user("user1")
        model1.trust_level = 0.8
        await modeling.storage.save(model1)

        model2 = await modeling.get_or_create_user("user1")
        assert model2.trust_level == 0.8

    @pytest.mark.asyncio
    async def test_get_or_create_user_uses_cache(self, modeling):
        """Test cache is used for repeated lookups."""
        model1 = await modeling.get_or_create_user("user1")
        model1.trust_level = 0.9
        modeling._cache["user1"] = model1

        model2 = await modeling.get_or_create_user("user1")
        assert model2.trust_level == 0.9

    @pytest.mark.asyncio
    async def test_extract_conclusions(self, modeling, mock_llm_client, mock_conclusions_response):
        """Test conclusion extraction from user message."""
        mock_llm_client.chat.return_value = mock_conclusions_response

        model = UserModel(user_id="user1")
        conclusions = await modeling.extract_conclusions(
            "I am vegan and love hiking",
            "No prior context",
            model,
        )

        assert len(conclusions) == 2
        assert conclusions[0].conclusion_type == "deductive"
        assert conclusions[0].confidence >= 0.5

    @pytest.mark.asyncio
    async def test_extract_conclusions_with_markdown(self, modeling, mock_llm_client):
        """Test parsing markdown code blocks in response."""
        response = MagicMock()
        response.content = (
            "```json\n"
            + json.dumps(
                {"conclusions": [{"type": "abductive", "conclusion": "Test", "confidence": 0.6}]}
            )
            + "\n```"
        )
        mock_llm_client.chat.return_value = response

        model = UserModel(user_id="user1")
        conclusions = await modeling.extract_conclusions("Test", "", model)

        assert len(conclusions) == 1
        assert conclusions[0].conclusion == "Test"

    @pytest.mark.asyncio
    async def test_extract_conclusions_low_confidence_filtered(self, modeling, mock_llm_client):
        """Test low-confidence conclusions are filtered out."""
        response = MagicMock()
        response.content = json.dumps(
            {
                "conclusions": [
                    {"type": "deductive", "conclusion": "High conf", "confidence": 0.8},
                    {"type": "inductive", "conclusion": "Low conf", "confidence": 0.3},
                ]
            }
        )
        mock_llm_client.chat.return_value = response

        model = UserModel(user_id="user1")
        conclusions = await modeling.extract_conclusions("Test", "", model)

        assert len(conclusions) == 1
        assert conclusions[0].conclusion == "High conf"

    @pytest.mark.asyncio
    async def test_extract_conclusions_malformed_json(self, modeling, mock_llm_client):
        """Test handling malformed JSON response."""
        response = MagicMock()
        response.content = "not valid json"
        mock_llm_client.chat.return_value = response

        model = UserModel(user_id="user1")
        conclusions = await modeling.extract_conclusions("Test", "", model)

        assert conclusions == []

    @pytest.mark.asyncio
    async def test_extract_conclusions_empty_list(self, modeling, mock_llm_client):
        """Test empty conclusions list."""
        response = MagicMock()
        response.content = json.dumps({"conclusions": []})
        mock_llm_client.chat.return_value = response

        model = UserModel(user_id="user1")
        conclusions = await modeling.extract_conclusions("Test", "", model)

        assert conclusions == []

    @pytest.mark.asyncio
    async def test_detect_preferences(self, modeling, mock_llm_client, mock_preferences_response):
        """Test preference detection."""
        mock_llm_client.chat.return_value = mock_preferences_response

        model = UserModel(user_id="user1")
        prefs = await modeling.detect_preferences("I prefer direct communication", model)

        assert len(prefs) == 2
        assert prefs[0].category == "communication"

    @pytest.mark.asyncio
    async def test_detect_preferences_low_confidence_filtered(self, modeling, mock_llm_client):
        """Test low-confidence preferences filtered."""
        response = MagicMock()
        response.content = json.dumps(
            {
                "preferences": [
                    {"category": "topic", "value": "AI", "confidence": 0.9},
                    {"category": "style", "value": "casual", "confidence": 0.4},
                ]
            }
        )
        mock_llm_client.chat.return_value = response

        model = UserModel(user_id="user1")
        prefs = await modeling.detect_preferences("Test", model)

        assert len(prefs) == 1
        assert prefs[0].value == "AI"

    @pytest.mark.asyncio
    async def test_detect_preferences_malformed_json(self, modeling, mock_llm_client):
        """Test handling malformed JSON."""
        response = MagicMock()
        response.content = "invalid json"
        mock_llm_client.chat.return_value = response

        model = UserModel(user_id="user1")
        prefs = await modeling.detect_preferences("Test", model)

        assert prefs == []

    @pytest.mark.asyncio
    async def test_detect_emotional_triggers(
        self, modeling, mock_llm_client, mock_triggers_response
    ):
        """Test emotional trigger detection."""
        mock_llm_client.chat.return_value = mock_triggers_response

        triggers = await modeling.detect_emotional_triggers(
            "I hate work deadlines but love family time"
        )

        assert "work deadlines" in triggers
        assert "family" in triggers
        assert triggers["work deadlines"] == 0.8

    @pytest.mark.asyncio
    async def test_detect_emotional_triggers_low_intensity_filtered(
        self, modeling, mock_llm_client
    ):
        """Test low-intensity triggers filtered."""
        response = MagicMock()
        response.content = json.dumps(
            {
                "triggers": [
                    {"topic": "Strong", "intensity": 0.8},
                    {"topic": "Weak", "intensity": 0.3},
                ]
            }
        )
        mock_llm_client.chat.return_value = response

        triggers = await modeling.detect_emotional_triggers("Test")

        assert "strong" in triggers
        assert "weak" not in triggers

    @pytest.mark.asyncio
    async def test_detect_emotional_triggers_malformed_json(self, modeling, mock_llm_client):
        """Test handling malformed JSON."""
        response = MagicMock()
        response.content = "bad json"
        mock_llm_client.chat.return_value = response

        triggers = await modeling.detect_emotional_triggers("Test")

        assert triggers == {}

    def test_update_relationship_metrics_positive(self, modeling):
        """Test trust increases with positive sentiment."""
        model = UserModel(user_id="user1")
        initial_trust = model.trust_level

        result = modeling.update_relationship_metrics(
            model, interaction_sentiment=0.8, interaction_depth=0.5
        )

        assert result.trust_level > initial_trust
        assert result.familiarity > 0.0

    def test_update_relationship_metrics_negative(self, modeling):
        """Test trust decreases with negative sentiment."""
        model = UserModel(user_id="user1")
        initial_trust = model.trust_level

        result = modeling.update_relationship_metrics(
            model, interaction_sentiment=-0.8, interaction_depth=0.5
        )

        assert result.trust_level < initial_trust

    def test_update_relationship_metrics_neutral(self, modeling):
        """Test neutral sentiment doesn't change trust much."""
        model = UserModel(user_id="user1")
        initial_trust = model.trust_level

        result = modeling.update_relationship_metrics(
            model, interaction_sentiment=0.1, interaction_depth=0.5
        )

        assert result.trust_level == initial_trust

    def test_update_relationship_metrics_deep_interaction(self, modeling):
        """Test deep interaction boosts trust."""
        model = UserModel(user_id="user1")
        initial_trust = model.trust_level

        result = modeling.update_relationship_metrics(
            model, interaction_sentiment=0.5, interaction_depth=0.8
        )

        assert result.trust_level > initial_trust

    def test_update_relationship_metrics_trust_boundary_0(self, modeling):
        """Test trust doesn't go below 0.0."""
        model = UserModel(user_id="user1")
        model.trust_level = 0.05

        result = modeling.update_relationship_metrics(
            model, interaction_sentiment=-1.0, interaction_depth=0.5
        )

        assert result.trust_level == 0.0

    def test_update_relationship_metrics_trust_boundary_1(self, modeling):
        """Test trust doesn't exceed 1.0."""
        model = UserModel(user_id="user1")
        model.trust_level = 0.98

        result = modeling.update_relationship_metrics(
            model, interaction_sentiment=1.0, interaction_depth=0.8
        )

        assert result.trust_level == 1.0

    @pytest.mark.asyncio
    async def test_query_user_preferences(self, modeling, mock_llm_client):
        """Test querying user preferences."""
        response = MagicMock()
        response.content = "User prefers direct communication and enjoys AI topics."
        mock_llm_client.chat.return_value = response

        model = await modeling.get_or_create_user("user1")
        model.add_preference(UserPreference(category="communication", value="direct"))
        model.peer_card.add_fact("[work] Software engineer")

        answer = await modeling.query_user_preferences("user1", "How do they communicate?")

        assert "direct" in answer or "communication" in answer

    @pytest.mark.asyncio
    async def test_query_user_preferences_error(self, modeling, mock_llm_client):
        """Test error handling in query."""
        mock_llm_client.chat.side_effect = RuntimeError("LLM error")

        answer = await modeling.query_user_preferences("user1", "Test?")

        assert "unable to answer" in answer

    @pytest.mark.asyncio
    async def test_build_user_context(self, modeling):
        """Test building user context for prompts."""
        model = await modeling.get_or_create_user("user1")
        model.add_preference(UserPreference(category="topic", value="AI", confidence=0.8))
        model.peer_card.add_fact("[work] Engineer")
        for _ in range(10):
            model.update_emotional_trigger("deadlines", 0.8)

        context = await modeling.build_user_context("user1")

        assert "User Profile" in context
        assert "Engineer" in context
        assert "AI" in context
        assert "deadlines" in context

    @pytest.mark.asyncio
    async def test_build_user_context_truncation(self, modeling):
        """Test context truncation for large profiles."""
        model = await modeling.get_or_create_user("user1")

        for i in range(50):
            model.peer_card.add_fact(f"Fact {i} with lots of text to increase length")
            model.add_preference(
                UserPreference(category=f"cat{i}", value=f"val{i}", confidence=0.8)
            )

        context = await modeling.build_user_context("user1", max_tokens=100)

        assert "User Profile" in context

    @pytest.mark.asyncio
    async def test_build_user_context_empty_user(self, modeling):
        """Test building context for new user with no data."""
        context = await modeling.build_user_context("new_user")

        assert "User Profile" in context
        assert "trust=" in context

    @pytest.mark.asyncio
    async def test_analyze_sentiment(self, modeling, mock_llm_client):
        """Test sentiment analysis."""
        response = MagicMock()
        response.content = "0.75"
        mock_llm_client.chat.return_value = response

        sentiment = await modeling._analyze_sentiment("I love this!")

        assert sentiment == 0.75

    @pytest.mark.asyncio
    async def test_analyze_sentiment_negative(self, modeling, mock_llm_client):
        """Test negative sentiment."""
        response = MagicMock()
        response.content = "-0.6"
        mock_llm_client.chat.return_value = response

        sentiment = await modeling._analyze_sentiment("I hate this!")

        assert sentiment == -0.6

    @pytest.mark.asyncio
    async def test_analyze_sentiment_no_number(self, modeling, mock_llm_client):
        """Test sentiment when no number in response."""
        response = MagicMock()
        response.content = "positive"
        mock_llm_client.chat.return_value = response

        sentiment = await modeling._analyze_sentiment("Good")

        assert sentiment == 0.0

    @pytest.mark.asyncio
    async def test_analyze_sentiment_error(self, modeling, mock_llm_client):
        """Test sentiment analysis error handling."""
        mock_llm_client.chat.side_effect = RuntimeError("LLM error")

        sentiment = await modeling._analyze_sentiment("Test")

        assert sentiment == 0.0

    def test_calculate_interaction_depth_short(self, modeling):
        """Test depth for short message."""
        depth = modeling._calculate_interaction_depth("Hi")

        assert depth >= 0.0
        assert depth <= 1.0

    def test_calculate_interaction_depth_long(self, modeling):
        """Test depth for long personal message."""
        message = (
            "I feel really happy today because my work went well. "
            "I love my job and I feel grateful for my team. "
            "My boss gave me a great review and I feel excited about the future."
        )
        depth = modeling._calculate_interaction_depth(message)

        assert depth > 0.5

    def test_calculate_interaction_depth_with_pronouns(self, modeling):
        """Test depth with personal pronouns."""
        message = "I think my work is important to me"
        depth = modeling._calculate_interaction_depth(message)

        assert depth > 0.0

    def test_calculate_interaction_depth_with_emotion(self, modeling):
        """Test depth with emotional words."""
        message = "I feel sad and anxious about the situation"
        depth = modeling._calculate_interaction_depth(message)

        assert depth > 0.0

    def test_calculate_interaction_depth_empty(self, modeling):
        """Test depth for empty message."""
        depth = modeling._calculate_interaction_depth("")

        assert depth == 0.0

    @pytest.mark.asyncio
    async def test_get_user_summary(self, modeling):
        """Test getting user summary."""
        model = await modeling.get_or_create_user("user1")
        model.add_preference(UserPreference(category="topic", value="AI"))
        model.peer_card.add_fact("[work] Engineer")
        model.record_interaction({"test": True})

        summary = await modeling.get_user_summary("user1")

        assert summary["user_id"] == "user1"
        assert summary["relationship"]["trust_level"] == 0.3
        assert summary["peer_card"]["fact_count"] == 1
        assert summary["preferences"]["total"] == 1
        assert summary["conclusions"] == 0
        assert "first_interaction" in summary
        assert "last_interaction" in summary

    @pytest.mark.asyncio
    async def test_get_user_summary_empty_user(self, modeling):
        """Test summary for new user."""
        summary = await modeling.get_user_summary("new_user")

        assert summary["user_id"] == "new_user"
        assert summary["peer_card"]["fact_count"] == 0
        assert summary["preferences"]["total"] == 0

    @pytest.mark.asyncio
    async def test_update_from_interaction_full(
        self,
        modeling,
        mock_llm_client,
        mock_conclusions_response,
        mock_preferences_response,
        mock_triggers_response,
        mock_sentiment_response,
    ):
        """Test full interaction update flow."""

        async def mock_chat(*args, **kwargs):
            messages = kwargs.get("messages", args[0] if args else [])
            prompt = messages[1]["content"] if len(messages) > 1 else ""
            if "conclusions" in prompt.lower():
                return mock_conclusions_response
            elif "preferences" in prompt.lower():
                return mock_preferences_response
            elif "emotional triggers" in prompt.lower():
                return mock_triggers_response
            else:
                return mock_sentiment_response

        mock_llm_client.chat.side_effect = mock_chat

        model = await modeling.update_from_interaction(
            user_id="user1",
            user_message="I am vegan and love hiking. I prefer direct communication.",
            assistant_message="That's great to know!",
            interaction_id="int_123",
        )

        assert model.user_id == "user1"
        assert len(model.conclusions) == 2
        assert len(model.preferences) == 2
        assert len(model.emotional_triggers) == 2
        assert model.interaction_count == 1
        assert model.total_messages == 2

    @pytest.mark.asyncio
    async def test_update_from_interaction_empty_message(self, modeling, mock_llm_client):
        """Test handling empty user message."""

        async def mock_chat(*args, **kwargs):
            response = MagicMock()
            response.content = json.dumps({"conclusions": [], "preferences": [], "triggers": []})
            return response

        mock_llm_client.chat.side_effect = mock_chat

        model = await modeling.update_from_interaction(
            user_id="user1",
            user_message="",
            assistant_message="I see.",
        )

        assert model.user_id == "user1"
        assert model.interaction_count == 1

    @pytest.mark.asyncio
    async def test_update_from_interaction_with_emotional_state(self, modeling, mock_llm_client):
        """Test update with emotional state parameter."""

        async def mock_chat(*args, **kwargs):
            response = MagicMock()
            response.content = json.dumps({"triggers": []})
            return response

        mock_llm_client.chat.side_effect = mock_chat

        model = await modeling.update_from_interaction(
            user_id="user1",
            user_message="Test",
            assistant_message="Response",
            emotional_state={"mood": "happy"},
        )

        assert model is not None


class TestEdgeCases:
    """Edge case tests for user modeling system."""

    @pytest.mark.asyncio
    async def test_empty_messages(self):
        """Test handling completely empty messages."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)

        response = MagicMock()
        response.content = json.dumps(
            {
                "conclusions": [],
                "preferences": [],
                "triggers": [],
            }
        )
        client.chat.return_value = response

        model = await modeling.update_from_interaction(
            user_id="user1",
            user_message="",
            assistant_message="",
        )

        assert model.interaction_count == 1

    @pytest.mark.asyncio
    async def test_malformed_llm_json(self):
        """Test handling completely malformed LLM JSON."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)

        response = MagicMock()
        response.content = "This is not JSON at all!"
        client.chat.return_value = response

        conclusions = await modeling.extract_conclusions("Test", "", UserModel(user_id="u1"))
        assert conclusions == []

        preferences = await modeling.detect_preferences("Test", UserModel(user_id="u1"))
        assert preferences == []

        triggers = await modeling.detect_emotional_triggers("Test")
        assert triggers == {}

    @pytest.mark.asyncio
    async def test_boundary_trust_0(self):
        """Test trust level at 0.0 boundary."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)

        model = UserModel(user_id="user1", trust_level=0.0)
        result = modeling.update_relationship_metrics(
            model, interaction_sentiment=-1.0, interaction_depth=0.5
        )

        assert result.trust_level == 0.0

    @pytest.mark.asyncio
    async def test_boundary_trust_1(self):
        """Test trust level at 1.0 boundary."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)

        model = UserModel(user_id="user1", trust_level=1.0)
        result = modeling.update_relationship_metrics(
            model, interaction_sentiment=1.0, interaction_depth=0.8
        )

        assert result.trust_level == 1.0

    def test_peer_card_exactly_40_facts(self):
        """Test peer card at exactly 40 facts boundary."""
        card = UserPeerCard()

        for i in range(40):
            card.add_fact(f"Fact {i}")

        assert len(card.facts) == 40

        card.add_fact("Fact 40")
        assert len(card.facts) == 40
        assert card.facts[-1] == "Fact 40"

    def test_preference_reinforce_from_0_1(self):
        """Test reinforcing from minimum confidence."""
        p = UserPreference(category="test", value="val", confidence=0.1)
        p.reinforce()

        assert p.confidence > 0.1
        assert p.confidence < 1.0

    def test_preference_contradict_to_minimum(self):
        """Test contradicting down to minimum."""
        p = UserPreference(category="test", value="val", confidence=0.2)
        p.contradict()
        p.contradict()
        p.contradict()

        assert p.confidence == 0.1
        assert p.evidence_count == 1

    @pytest.mark.asyncio
    async def test_storage_pagination_large_offset(self):
        """Test pagination with offset larger than dataset."""
        storage = InMemoryUserModelStorage()
        await storage.save(UserModel(user_id="user1"))

        result = await storage.list_users(offset=100, limit=10)
        assert result == []

    def test_conclusion_confidence_boundary(self):
        """Test conclusion at confidence boundaries."""
        c_low = Conclusion(conclusion_type="deductive", conclusion="Test", confidence=0.0)
        c_high = Conclusion(conclusion_type="inductive", conclusion="Test", confidence=1.0)

        assert c_low.confidence == 0.0
        assert c_high.confidence == 1.0

    @pytest.mark.asyncio
    async def test_sentiment_extraction_various_formats(self):
        """Test sentiment extraction with various number formats."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        test_cases = [
            ("0.75", 0.75),
            ("-0.5", -0.5),
            ("The sentiment is 0.8", 0.8),
            ("Score: -0.3 out of 1", -0.3),
        ]

        for content, expected in test_cases:
            response = MagicMock()
            response.content = content
            client.chat.return_value = response

            sentiment = await modeling._analyze_sentiment("Test")
            assert sentiment == expected, f"Failed for content: {content}"

    @pytest.mark.asyncio
    async def test_sentiment_clamping(self):
        """Test sentiment is clamped to [-1, 1]."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        response = MagicMock()
        response.content = "2.5"
        client.chat.return_value = response

        sentiment = await modeling._analyze_sentiment("Test")
        assert sentiment == 1.0

        response.content = "-2.0"
        sentiment = await modeling._analyze_sentiment("Test")
        assert sentiment == -1.0

    def test_interaction_depth_maximum(self):
        """Test interaction depth capped at 1.0."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        message = (
            "I feel happy and sad and angry and worried and excited and love and hate and enjoy and upset and grateful and frustrated and anxious and hopeful. "
            * 10
        )
        message += "I me my mine myself " * 20

        depth = modeling._calculate_interaction_depth(message)
        assert depth == 1.0

    @pytest.mark.asyncio
    async def test_build_context_no_significant_triggers(self):
        """Test context when no triggers meet threshold."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        model = await modeling.get_or_create_user("user1")
        model.update_emotional_trigger("minor", 0.3)

        context = await modeling.build_user_context("user1")

        assert "Sensitive Topics" not in context

    @pytest.mark.asyncio
    async def test_query_user_preferences_empty_model(self):
        """Test query with completely empty user model."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        response = MagicMock()
        response.content = "I don't have enough information."
        client.chat.return_value = response

        answer = await modeling.query_user_preferences("new_user", "What do they like?")

        assert isinstance(answer, str)

    @pytest.mark.asyncio
    async def test_llm_exception_in_extract_conclusions(self):
        """Test LLM exception handling in extract_conclusions."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        client.chat.side_effect = RuntimeError("LLM failed")

        conclusions = await modeling.extract_conclusions("Test", "", UserModel(user_id="u1"))
        assert conclusions == []

    @pytest.mark.asyncio
    async def test_llm_exception_in_detect_preferences(self):
        """Test LLM exception handling in detect_preferences."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        client.chat.side_effect = RuntimeError("LLM failed")

        prefs = await modeling.detect_preferences("Test", UserModel(user_id="u1"))
        assert prefs == []

    @pytest.mark.asyncio
    async def test_llm_exception_in_detect_triggers(self):
        """Test LLM exception handling in detect_emotional_triggers."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        client.chat.side_effect = RuntimeError("LLM failed")

        triggers = await modeling.detect_emotional_triggers("Test")
        assert triggers == {}

    def test_user_model_storage_abstract(self):
        """Test that UserModelStorage cannot be instantiated."""
        with pytest.raises(TypeError):
            UserModelStorage()

    @pytest.mark.asyncio
    async def test_update_from_interaction_records_pattern(self):
        """Test that interaction patterns are recorded correctly."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        response = MagicMock()
        response.content = json.dumps(
            {
                "conclusions": [],
                "preferences": [],
                "triggers": [],
            }
        )
        client.chat.return_value = response

        model = await modeling.update_from_interaction(
            user_id="user1",
            user_message="Hello?",
            assistant_message="Hi!",
        )

        assert len(model.interaction_patterns) == 1
        pattern = model.interaction_patterns[0]
        assert "sentiment" in pattern
        assert "depth" in pattern
        assert "message_length" in pattern
        assert "has_question" in pattern
        assert pattern["has_question"] is True
        assert pattern["message_length"] == 6

    @pytest.mark.asyncio
    async def test_build_extraction_context_empty(self):
        """Test extraction context for new user."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        model = UserModel(user_id="new_user")
        context = await modeling._build_extraction_context(model)

        assert context == "No prior information about this user."

    @pytest.mark.asyncio
    async def test_build_extraction_context_with_data(self):
        """Test extraction context with existing data."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        model = UserModel(user_id="user1")
        model.peer_card.add_fact("[work] Engineer")
        model.add_preference(UserPreference(category="topic", value="AI"))

        context = await modeling._build_extraction_context(model)

        assert "Known facts:" in context
        assert "Engineer" in context
        assert "Known preferences:" in context
        assert "AI" in context

    def test_user_model_preferred_style(self):
        """Test user model preferred style field."""
        model = UserModel(user_id="user1", preferred_style="formal")
        assert model.preferred_style == "formal"

    @pytest.mark.asyncio
    async def test_get_user_summary_with_last_interaction(self):
        """Test summary includes last interaction time."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        model = await modeling.get_or_create_user("user1")
        model.record_interaction({"test": True})

        summary = await modeling.get_user_summary("user1")

        assert summary["last_interaction"] is not None
        assert summary["relationship"]["interaction_count"] == 1

    @pytest.mark.asyncio
    async def test_preference_category_counting(self):
        """Test preference counting by category in summary."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        model = await modeling.get_or_create_user("user1")
        model.add_preference(UserPreference(category="communication", value="direct"))
        model.add_preference(UserPreference(category="communication", value="brief"))
        model.add_preference(UserPreference(category="topic", value="AI"))

        summary = await modeling.get_user_summary("user1")

        by_category = summary["preferences"]["by_category"]
        assert by_category["communication"] == 2
        assert by_category["topic"] == 1

    def test_conclusion_default_datetime(self):
        """Test conclusion gets default datetime."""
        before = datetime.now()
        c = Conclusion(conclusion_type="deductive", conclusion="Test")
        after = datetime.now()

        assert before <= c.created_at <= after

    def test_user_model_default_datetime(self):
        """Test user model gets default datetime."""
        before = datetime.now()
        model = UserModel(user_id="user1")
        after = datetime.now()

        assert before <= model.first_interaction_at <= after
        assert before <= model.updated_at <= after

    @pytest.mark.asyncio
    async def test_detect_triggers_with_empty_topic(self):
        """Test triggers with empty topic are filtered."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        response = MagicMock()
        response.content = json.dumps(
            {
                "triggers": [
                    {"topic": "valid", "intensity": 0.8},
                    {"topic": "", "intensity": 0.9},
                ]
            }
        )
        client.chat.return_value = response

        triggers = await modeling.detect_emotional_triggers("Test")

        assert "valid" in triggers
        assert "" not in triggers

    @pytest.mark.asyncio
    async def test_conclusion_with_markdown_backticks(self):
        """Test conclusion extraction with triple backticks."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        response = MagicMock()
        response.content = (
            "```\n"
            + json.dumps(
                {"conclusions": [{"type": "deductive", "conclusion": "Test", "confidence": 0.7}]}
            )
            + "\n```"
        )
        client.chat.return_value = response

        conclusions = await modeling.extract_conclusions("Test", "", UserModel(user_id="u1"))
        assert len(conclusions) == 1

    @pytest.mark.asyncio
    async def test_preference_with_markdown_backticks(self):
        """Test preference detection with triple backticks."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        response = MagicMock()
        response.content = (
            "```\n"
            + json.dumps({"preferences": [{"category": "topic", "value": "AI", "confidence": 0.8}]})
            + "\n```"
        )
        client.chat.return_value = response

        prefs = await modeling.detect_preferences("Test", UserModel(user_id="u1"))
        assert len(prefs) == 1

    @pytest.mark.asyncio
    async def test_trigger_with_markdown_backticks(self):
        """Test trigger detection with triple backticks."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        response = MagicMock()
        response.content = (
            "```\n" + json.dumps({"triggers": [{"topic": "work", "intensity": 0.8}]}) + "\n```"
        )
        client.chat.return_value = response

        triggers = await modeling.detect_emotional_triggers("Test")
        assert "work" in triggers

    def test_user_model_from_dict_complex(self):
        """Test round-trip serialization with complex data."""
        model = UserModel(user_id="user1")
        model.add_conclusion(
            Conclusion(
                conclusion_type="deductive",
                conclusion="User likes Python",
                confidence=0.8,
            )
        )
        model.add_preference(UserPreference(category="topic", value="AI", confidence=0.9))
        model.peer_card.add_fact("[work] Engineer")
        model.update_emotional_trigger("deadlines", 0.8)
        model.record_interaction({"sentiment": 0.5})

        data = model.to_dict()
        restored = UserModel.from_dict(data)

        assert restored.user_id == "user1"
        assert len(restored.conclusions) == 1
        assert len(restored.preferences) == 1
        assert len(restored.peer_card.facts) == 2  # 1 from conclusion + 1 explicit
        assert restored.emotional_triggers["deadlines"] == 0.24
        assert len(restored.interaction_patterns) == 1

    @pytest.mark.asyncio
    async def test_update_from_interaction_saves_to_storage(self):
        """Test that update_from_interaction persists to storage."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        response = MagicMock()
        response.content = json.dumps(
            {
                "conclusions": [],
                "preferences": [],
                "triggers": [],
            }
        )
        client.chat.return_value = response

        await modeling.update_from_interaction(
            user_id="user1",
            user_message="Test",
            assistant_message="Response",
        )

        stored = await modeling.storage.get("user1")
        assert stored is not None
        assert stored.user_id == "user1"
        assert stored.interaction_count == 1

    @pytest.mark.asyncio
    async def test_update_from_interaction_updates_cache(self):
        """Test that update_from_interaction updates cache."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        response = MagicMock()
        response.content = json.dumps(
            {
                "conclusions": [],
                "preferences": [],
                "triggers": [],
            }
        )
        client.chat.return_value = response

        await modeling.update_from_interaction(
            user_id="user1",
            user_message="Test",
            assistant_message="Response",
        )

        assert "user1" in modeling._cache
        assert modeling._cache["user1"].interaction_count == 1

    def test_calculate_interaction_depth_no_emotional_words(self):
        """Test depth calculation without emotional words."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        message = "The weather is nice today. It is sunny and warm."
        depth = modeling._calculate_interaction_depth(message)

        assert depth >= 0.0
        assert depth < 0.8

    def test_calculate_interaction_depth_only_pronouns(self):
        """Test depth with only personal pronouns."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        message = "I me my mine myself"
        depth = modeling._calculate_interaction_depth(message)

        assert depth > 0.0

    def test_relationship_metrics_familiarity_growth(self):
        """Test familiarity grows with each interaction."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        model = UserModel(user_id="user1")
        initial = model.familiarity

        for _ in range(10):
            model = modeling.update_relationship_metrics(
                model, interaction_sentiment=0.5, interaction_depth=0.5
            )

        assert model.familiarity > initial
        assert model.familiarity <= 1.0

    def test_peer_card_access_fact_updates_timestamp(self):
        """Test that access_fact updates the timestamp."""
        card = UserPeerCard()
        card.add_fact("Fact A")

        old_ts = card.access_timestamps[0]
        import time

        time.sleep(0.01)

        card.access_fact("Fact A")
        new_ts = card.access_timestamps[0]

        assert new_ts >= old_ts

    def test_user_preference_default_values(self):
        """Test UserPreference default values."""
        p = UserPreference(category="test", value="val")

        assert p.confidence == 0.5
        assert p.evidence_count == 1
        assert p.learned_from == ""
        assert isinstance(p.learned_at, datetime)
        assert isinstance(p.last_reinforced_at, datetime)

    @pytest.mark.asyncio
    async def test_build_user_context_with_preferred_style(self):
        """Test context includes preferred style."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        model = await modeling.get_or_create_user("user1")
        model.preferred_style = "casual"

        context = await modeling.build_user_context("user1")

        assert "casual" in context

    @pytest.mark.asyncio
    async def test_query_user_preferences_with_conclusions(self):
        """Test query includes high-confidence conclusions."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        response = MagicMock()
        response.content = "User knows Python well."
        client.chat.return_value = response

        model = await modeling.get_or_create_user("user1")
        model.add_conclusion(
            Conclusion(
                conclusion_type="deductive",
                conclusion="User knows Python",
                confidence=0.8,
            )
        )

        answer = await modeling.query_user_preferences("user1", "What does user know?")
        assert isinstance(answer, str)

    @pytest.mark.asyncio
    async def test_list_users_with_custom_storage(self):
        """Test list_users with custom storage implementation."""
        storage = InMemoryUserModelStorage()
        modeling = AdaptiveUserModeling(llm_client=AsyncMock(), storage=storage)

        for i in range(5):
            await modeling.storage.save(UserModel(user_id=f"user{i}"))

        users = await modeling.storage.list_users(limit=3)
        assert len(users) == 3

    def test_adaptive_modeling_default_storage(self):
        """Test AdaptiveUserModeling creates default in-memory storage."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)

        assert isinstance(modeling.storage, InMemoryUserModelStorage)

    @pytest.mark.asyncio
    async def test_conclusion_with_premises(self):
        """Test conclusion extraction preserves premises."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        response = MagicMock()
        response.content = json.dumps(
            {
                "conclusions": [
                    {
                        "type": "deductive",
                        "premises": ["User says X", "User says Y"],
                        "conclusion": "User believes Z",
                        "confidence": 0.8,
                    }
                ]
            }
        )
        client.chat.return_value = response

        conclusions = await modeling.extract_conclusions("Test", "", UserModel(user_id="u1"))
        assert len(conclusions) == 1
        assert len(conclusions[0].premises) == 2
        assert conclusions[0].premises[0] == "User says X"

    @pytest.mark.asyncio
    async def test_preference_with_evidence(self):
        """Test preference detection ignores evidence field."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        response = MagicMock()
        response.content = json.dumps(
            {
                "preferences": [
                    {
                        "category": "topic",
                        "value": "AI",
                        "confidence": 0.8,
                        "evidence": "User mentions AI often",
                    }
                ]
            }
        )
        client.chat.return_value = response

        prefs = await modeling.detect_preferences("Test", UserModel(user_id="u1"))
        assert len(prefs) == 1
        assert prefs[0].category == "topic"
        assert prefs[0].value == "AI"

    def test_user_model_interaction_count_tracking(self):
        """Test interaction count increments correctly."""
        model = UserModel(user_id="user1")

        for i in range(5):
            model.record_interaction({"index": i})

        assert model.interaction_count == 5
        assert model.total_messages == 10

    @pytest.mark.asyncio
    async def test_empty_conclusions_response(self):
        """Test empty conclusions array in response."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        response = MagicMock()
        response.content = json.dumps({"conclusions": []})
        client.chat.return_value = response

        conclusions = await modeling.extract_conclusions("Test", "", UserModel(user_id="u1"))
        assert conclusions == []

    @pytest.mark.asyncio
    async def test_empty_preferences_response(self):
        """Test empty preferences array in response."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        response = MagicMock()
        response.content = json.dumps({"preferences": []})
        client.chat.return_value = response

        prefs = await modeling.detect_preferences("Test", UserModel(user_id="u1"))
        assert prefs == []

    @pytest.mark.asyncio
    async def test_empty_triggers_response(self):
        """Test empty triggers array in response."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        response = MagicMock()
        response.content = json.dumps({"triggers": []})
        client.chat.return_value = response

        triggers = await modeling.detect_emotional_triggers("Test")
        assert triggers == {}

    def test_peer_card_get_facts_no_match(self):
        """Test get_facts with category that has no matches."""
        card = UserPeerCard()
        card.add_fact("[work] Engineer")

        result = card.get_facts(category="hobby")
        assert result == []

    def test_user_model_add_preference_multiple_categories(self):
        """Test adding preferences across multiple categories."""
        model = UserModel(user_id="user1")
        model.add_preference(UserPreference(category="communication", value="direct"))
        model.add_preference(UserPreference(category="topic", value="AI"))
        model.add_preference(UserPreference(category="style", value="formal"))

        assert len(model.preferences) == 3
        assert len(model.get_preferences_by_category("communication")) == 1
        assert len(model.get_preferences_by_category("topic")) == 1
        assert len(model.get_preferences_by_category("style")) == 1

    @pytest.mark.asyncio
    async def test_update_from_interaction_no_interaction_id(self):
        """Test update without interaction_id."""
        client = AsyncMock()
        modeling = AdaptiveUserModeling(llm_client=client)
        response = MagicMock()
        response.content = json.dumps(
            {
                "conclusions": [],
                "preferences": [],
                "triggers": [],
            }
        )
        client.chat.return_value = response

        model = await modeling.update_from_interaction(
            user_id="user1",
            user_message="Test",
            assistant_message="Response",
        )

        assert model is not None
        assert model.interaction_count == 1
