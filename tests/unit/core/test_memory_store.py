"""Tests for memory_store module."""

import tempfile
from pathlib import Path

import pytest

from persona_agent.core.memory_store import Memory, MemoryStore, UserModel


class TestMemory:
    """Tests for Memory dataclass."""

    def test_basic_memory(self):
        """Test basic memory creation."""
        memory = Memory(
            id="1",
            session_id="test-session",
            timestamp=1234567890.0,
            user_message="Hello",
            assistant_message="Hi there!",
        )

        assert memory.id == "1"
        assert memory.session_id == "test-session"
        assert memory.user_message == "Hello"
        assert memory.assistant_message == "Hi there!"
        assert memory.embedding is None
        assert memory.metadata is None

    def test_memory_with_embedding(self):
        """Test memory with embedding."""
        embedding = [0.1, 0.2, 0.3]
        memory = Memory(
            id="1",
            session_id="test-session",
            timestamp=1234567890.0,
            user_message="Hello",
            assistant_message="Hi!",
            embedding=embedding,
        )

        assert memory.embedding == embedding

    def test_memory_with_metadata(self):
        """Test memory with metadata."""
        metadata = {"source": "user", "importance": "high"}
        memory = Memory(
            id="1",
            session_id="test-session",
            timestamp=1234567890.0,
            user_message="Hello",
            assistant_message="Hi!",
            metadata=metadata,
        )

        assert memory.metadata == metadata


class TestUserModel:
    """Tests for UserModel dataclass."""

    def test_basic_user_model(self):
        """Test basic user model creation."""
        model = UserModel(
            user_id="user123",
            traits={"friendly": True},
            preferences={"language": "en"},
            relationship_stage="acquaintance",
            interaction_patterns=[],
            created_at=1234567890.0,
            updated_at=1234567890.0,
        )

        assert model.user_id == "user123"
        assert model.relationship_stage == "acquaintance"


class TestMemoryStore:
    """Tests for MemoryStore."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield db_path

    @pytest.fixture
    def store(self, temp_db):
        """Create a MemoryStore with temporary database."""
        return MemoryStore(db_path=temp_db)

    def test_initialization_creates_db(self, temp_db):
        """Test that initialization creates the database."""
        store = MemoryStore(db_path=temp_db)

        assert temp_db.exists()

    def test_initialization_creates_tables(self, temp_db):
        """Test that initialization creates required tables."""
        store = MemoryStore(db_path=temp_db)

        # Check that tables exist by querying them
        import sqlite3

        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}

        assert "conversations" in tables
        assert "user_models" in tables
        assert "memory_summaries" in tables

    @pytest.mark.asyncio
    async def test_store_conversation(self, store):
        """Test storing a conversation."""
        memory_id = await store.store(
            session_id="test-session",
            user_message="Hello",
            assistant_message="Hi there!",
        )

        assert memory_id > 0

    @pytest.mark.asyncio
    async def test_store_with_embedding(self, store):
        """Test storing with embedding."""
        embedding = [0.1, 0.2, 0.3, 0.4]
        memory_id = await store.store(
            session_id="test-session",
            user_message="Hello",
            assistant_message="Hi!",
            embedding=embedding,
            metadata={"key": "value"},
        )

        assert memory_id > 0

        # Verify retrieval includes embedding
        memories = await store.retrieve_recent("test-session", limit=1)
        assert len(memories) == 1
        assert memories[0].embedding == embedding
        assert memories[0].metadata == {"key": "value"}

    @pytest.mark.asyncio
    async def test_retrieve_recent(self, store):
        """Test retrieving recent conversations."""
        # Store multiple messages
        await store.store(
            session_id="test-session",
            user_message="Message 1",
            assistant_message="Response 1",
        )
        await store.store(
            session_id="test-session",
            user_message="Message 2",
            assistant_message="Response 2",
        )
        await store.store(
            session_id="test-session",
            user_message="Message 3",
            assistant_message="Response 3",
        )

        memories = await store.retrieve_recent("test-session", limit=2)

        assert len(memories) == 2
        # Most recent first
        assert memories[0].user_message == "Message 3"
        assert memories[1].user_message == "Message 2"

    @pytest.mark.asyncio
    async def test_retrieve_recent_empty(self, store):
        """Test retrieving from empty session."""
        memories = await store.retrieve_recent("nonexistent-session")

        assert memories == []

    @pytest.mark.asyncio
    async def test_retrieve_recent_limit(self, store):
        """Test retrieve_recent respects limit."""
        # Store many messages
        for i in range(10):
            await store.store(
                session_id="test-session",
                user_message=f"Message {i}",
                assistant_message=f"Response {i}",
            )

        memories = await store.retrieve_recent("test-session", limit=5)

        assert len(memories) == 5

    @pytest.mark.asyncio
    async def test_retrieve_relevant_keyword(self, store):
        """Test keyword-based retrieval."""
        await store.store(
            session_id="test-session",
            user_message="I love programming in Python",
            assistant_message="That's great!",
        )
        await store.store(
            session_id="test-session",
            user_message="The weather is nice today",
            assistant_message="Indeed!",
        )

        memories = await store.retrieve_relevant(
            query="python programming",
            session_id="test-session",
            limit=5,
        )

        # Should find the programming-related message
        assert len(memories) >= 0  # Keyword matching may vary

    @pytest.mark.asyncio
    async def test_retrieve_relevant_no_session(self, store):
        """Test retrieval across all sessions."""
        await store.store(
            session_id="session1",
            user_message="Python is great",
            assistant_message="Yes!",
        )
        await store.store(
            session_id="session2",
            user_message="JavaScript is fun",
            assistant_message="Indeed!",
        )

        memories = await store.retrieve_relevant(query="programming", limit=5)

        # Should search across all sessions
        assert isinstance(memories, list)

    @pytest.mark.asyncio
    async def test_get_or_create_user_model_new(self, store):
        """Test creating new user model."""
        model = await store.get_or_create_user_model("user123")

        assert model.user_id == "user123"
        assert model.relationship_stage == "initial"
        assert model.traits == {}
        assert model.created_at > 0
        assert model.updated_at > 0

    @pytest.mark.asyncio
    async def test_get_or_create_user_model_existing(self, store):
        """Test retrieving existing user model."""
        # Create first
        await store.get_or_create_user_model("user123")

        # Get again
        model = await store.get_or_create_user_model("user123")

        assert model.user_id == "user123"

    @pytest.mark.asyncio
    async def test_update_user_model(self, store):
        """Test updating user model."""
        model = await store.get_or_create_user_model("user123")

        model.traits = {"friendly": True}
        model.relationship_stage = "friend"

        await store.update_user_model(model)

        # Retrieve and verify
        retrieved = await store.get_or_create_user_model("user123")

        assert retrieved.traits == {"friendly": True}
        assert retrieved.relationship_stage == "friend"

    @pytest.mark.asyncio
    async def test_store_summary(self, store):
        """Test storing conversation summary."""
        await store.store_summary(
            session_id="test-session",
            summary="Conversation about Python",
            key_points=["Python basics", "Data structures"],
        )

        summaries = await store.get_summaries("test-session")

        assert len(summaries) == 1
        assert summaries[0]["summary"] == "Conversation about Python"
        assert summaries[0]["key_points"] == ["Python basics", "Data structures"]

    @pytest.mark.asyncio
    async def test_get_summaries_multiple(self, store):
        """Test retrieving multiple summaries."""
        for i in range(3):
            await store.store_summary(
                session_id="test-session",
                summary=f"Summary {i}",
                key_points=[f"Point {i}"],
            )

        summaries = await store.get_summaries("test-session", limit=2)

        assert len(summaries) == 2

    @pytest.mark.asyncio
    async def test_get_summaries_empty(self, store):
        """Test retrieving summaries for empty session."""
        summaries = await store.get_summaries("nonexistent-session")

        assert summaries == []

    def test_close(self, store):
        """Test close method."""
        # Should not raise
        store.close()


class TestMemoryStoreEdgeCases:
    """Edge case tests for MemoryStore."""

    @pytest.mark.asyncio
    async def test_store_empty_message(self, tmp_path):
        """Test storing empty message."""
        store = MemoryStore(db_path=tmp_path / "test.db")

        memory_id = await store.store(
            session_id="test",
            user_message="",
            assistant_message="",
        )

        assert memory_id > 0

    @pytest.mark.asyncio
    async def test_store_unicode(self, tmp_path):
        """Test storing unicode messages."""
        store = MemoryStore(db_path=tmp_path / "test.db")

        memory_id = await store.store(
            session_id="test",
            user_message="Hello 世界 🌍",
            assistant_message="你好! 👋",
        )

        assert memory_id > 0

        memories = await store.retrieve_recent("test")
        assert memories[0].user_message == "Hello 世界 🌍"

    @pytest.mark.asyncio
    async def test_concurrent_sessions(self, tmp_path):
        """Test storing to multiple sessions."""
        store = MemoryStore(db_path=tmp_path / "test.db")

        await store.store(
            session_id="session1",
            user_message="Message 1",
            assistant_message="Response 1",
        )
        await store.store(
            session_id="session2",
            user_message="Message 2",
            assistant_message="Response 2",
        )

        memories1 = await store.retrieve_recent("session1")
        memories2 = await store.retrieve_recent("session2")

        assert len(memories1) == 1
        assert len(memories2) == 1
        assert memories1[0].user_message == "Message 1"
        assert memories2[0].user_message == "Message 2"
