"""Tests for memory store."""

import tempfile
from pathlib import Path

import pytest

from persona_agent.core.memory_store import Memory, MemoryStore, UserModel


class TestMemoryStore:
    """Test memory store functionality."""

    @pytest.fixture
    def memory_store(self):
        """Create a temporary memory store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_memory.db"
            store = MemoryStore(db_path)
            yield store

    @pytest.mark.asyncio
    async def test_store_conversation(self, memory_store):
        """Test storing a conversation exchange."""
        memory_id = await memory_store.store(
            session_id="test_session",
            user_message="Hello",
            assistant_message="Hi there!",
        )
        assert memory_id is not None
        assert isinstance(memory_id, int)

    @pytest.mark.asyncio
    async def test_retrieve_recent(self, memory_store):
        """Test retrieving recent memories."""
        # Store multiple exchanges
        for i in range(5):
            await memory_store.store(
                session_id="test_session",
                user_message=f"Message {i}",
                assistant_message=f"Response {i}",
            )

        # Retrieve recent (most recent first)
        memories = await memory_store.retrieve_recent("test_session", limit=3)
        assert len(memories) == 3
        # Most recent first: Message 4, 3, 2
        assert memories[0].user_message == "Message 4"
        assert memories[2].user_message == "Message 2"

    @pytest.mark.asyncio
    async def test_retrieve_relevant(self, memory_store):
        """Test retrieving relevant memories by keyword."""
        # Store memories
        await memory_store.store(
            session_id="test_session",
            user_message="I love Python programming",
            assistant_message="Python is great!",
        )
        await memory_store.store(
            session_id="test_session",
            user_message="The weather is nice",
            assistant_message="Yes, sunny day!",
        )

        # Search for Python-related memory
        results = await memory_store.retrieve_relevant("Python", session_id="test_session")
        assert len(results) > 0
        assert "Python" in results[0].user_message

    @pytest.mark.asyncio
    async def test_user_model_crud(self, memory_store):
        """Test user model create, read, update."""
        # Create user model
        model = await memory_store.get_or_create_user_model("user123")
        assert model.user_id == "user123"
        assert model.relationship_stage == "initial"

        # Update model
        model.traits["friendliness"] = 0.8
        model.preferences["topic"] = "technology"
        await memory_store.update_user_model(model)

        # Retrieve and verify
        retrieved = await memory_store.get_or_create_user_model("user123")
        assert retrieved.traits["friendliness"] == 0.8
        assert retrieved.preferences["topic"] == "technology"

    @pytest.mark.asyncio
    async def test_memory_with_embedding(self, memory_store):
        """Test storing memory with embedding vector."""
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        await memory_store.store(
            session_id="test_session",
            user_message="Test message",
            assistant_message="Test response",
            embedding=embedding,
        )

        memories = await memory_store.retrieve_recent("test_session")
        assert len(memories) == 1
        assert memories[0].embedding == embedding

    @pytest.mark.asyncio
    async def test_memory_with_metadata(self, memory_store):
        """Test storing memory with metadata."""
        metadata = {"mood": "happy", "topic": "greeting"}
        await memory_store.store(
            session_id="test_session",
            user_message="Hi",
            assistant_message="Hello!",
            metadata=metadata,
        )

        memories = await memory_store.retrieve_recent("test_session")
        assert memories[0].metadata == metadata

    @pytest.mark.asyncio
    async def test_store_summary(self, memory_store):
        """Test storing conversation summary."""
        await memory_store.store_summary(
            session_id="test_session",
            summary="We discussed Python programming",
            key_points=["Python basics", "Variables", "Functions"],
        )

        summaries = await memory_store.get_summaries("test_session")
        assert len(summaries) == 1
        assert summaries[0]["summary"] == "We discussed Python programming"
        assert len(summaries[0]["key_points"]) == 3

    @pytest.mark.asyncio
    async def test_multiple_sessions(self, memory_store):
        """Test memory isolation between sessions."""
        # Store in session 1
        await memory_store.store(
            session_id="session_1",
            user_message="Session 1 message",
            assistant_message="Response 1",
        )

        # Store in session 2
        await memory_store.store(
            session_id="session_2",
            user_message="Session 2 message",
            assistant_message="Response 2",
        )

        # Verify isolation
        memories_1 = await memory_store.retrieve_recent("session_1")
        memories_2 = await memory_store.retrieve_recent("session_2")

        assert len(memories_1) == 1
        assert len(memories_2) == 1
        assert memories_1[0].user_message == "Session 1 message"
        assert memories_2[0].user_message == "Session 2 message"


class TestMemoryDataclass:
    """Test Memory dataclass."""

    def test_memory_creation(self):
        """Test creating a Memory object."""
        memory = Memory(
            id="123",
            session_id="test",
            timestamp=1234567890.0,
            user_message="Hello",
            assistant_message="Hi",
        )
        assert memory.id == "123"
        assert memory.session_id == "test"
        assert memory.user_message == "Hello"


class TestUserModelDataclass:
    """Test UserModel dataclass."""

    def test_user_model_creation(self):
        """Test creating a UserModel object."""
        model = UserModel(
            user_id="user123",
            traits={"openness": 0.8},
            preferences={"topic": "tech"},
            relationship_stage="acquaintance",
            interaction_patterns=[],
            created_at=1234567890.0,
            updated_at=1234567890.0,
        )
        assert model.user_id == "user123"
        assert model.traits["openness"] == 0.8
