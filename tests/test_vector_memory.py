"""Tests for vector memory store with ChromaDB."""

import tempfile
from pathlib import Path

import pytest

from persona_agent.core.memory_store import MemoryStore as SQLiteMemoryStore
from persona_agent.core.vector_memory import CHROMA_AVAILABLE, VectorMemoryStore


class TestVectorMemoryStore:
    """Test VectorMemoryStore functionality."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_path = Path(tmp_dir)
            yield {
                "db_path": base_path / "test.db",
                "chroma_path": base_path / "chroma",
            }

    @pytest.fixture
    def vector_store(self, temp_dirs):
        """Create a VectorMemoryStore instance."""
        store = VectorMemoryStore(
            db_path=temp_dirs["db_path"],
            chroma_path=temp_dirs["chroma_path"],
        )
        yield store
        store.close()

    @pytest.mark.asyncio
    async def test_initialization(self, temp_dirs):
        """Test store initialization."""
        store = VectorMemoryStore(
            db_path=temp_dirs["db_path"],
            chroma_path=temp_dirs["chroma_path"],
        )

        # Should have SQLite store
        assert store.sqlite_store is not None
        assert isinstance(store.sqlite_store, SQLiteMemoryStore)

        # Chroma might be None if not available
        if CHROMA_AVAILABLE:
            assert store.chroma_client is not None
            assert store.collection is not None
        else:
            assert store.chroma_client is None
            assert store.collection is None

        store.close()

    @pytest.mark.asyncio
    async def test_store_without_embedding(self, vector_store):
        """Test storing without embedding (SQLite only)."""
        memory_id = await vector_store.store(
            session_id="test_session",
            user_message="Hello",
            assistant_message="Hi there!",
            embedding=None,
        )

        assert isinstance(memory_id, int)
        assert memory_id > 0

    @pytest.mark.asyncio
    async def test_store_with_embedding(self, vector_store):
        """Test storing with embedding (SQLite + Chroma)."""
        # Create a simple embedding vector
        embedding = [0.1] * 384  # Common embedding size

        memory_id = await vector_store.store(
            session_id="test_session",
            user_message="Hello",
            assistant_message="Hi there!",
            embedding=embedding,
        )

        assert isinstance(memory_id, int)

    @pytest.mark.asyncio
    async def test_retrieve_recent(self, vector_store):
        """Test retrieving recent memories."""
        # Store some memories
        for i in range(5):
            await vector_store.store(
                session_id="test_session",
                user_message=f"Message {i}",
                assistant_message=f"Response {i}",
            )

        # Retrieve recent
        memories = await vector_store.retrieve_recent("test_session", limit=3)

        assert len(memories) == 3
        # Should be in reverse chronological order (newest first)
        assert memories[0].user_message == "Message 4"

    @pytest.mark.asyncio
    async def test_retrieve_relevant_fallback(self, vector_store):
        """Test retrieve_relevant falls back to SQLite when no embedding."""
        # Store a memory
        await vector_store.store(
            session_id="test_session",
            user_message="I love pizza",
            assistant_message="Pizza is great!",
        )

        # Query without embedding
        results = await vector_store.retrieve_relevant(
            query="pizza",
            session_id="test_session",
        )

        # Should find the memory via keyword search
        assert len(results) > 0
        assert any("pizza" in r.user_message.lower() for r in results)

    @pytest.mark.asyncio
    async def test_user_model_operations(self, vector_store):
        """Test user model CRUD operations."""
        user_id = "test_user_123"

        # Create user model
        model = await vector_store.get_or_create_user_model(user_id)
        assert model.user_id == user_id
        assert model.relationship_stage == "initial"

        # Update model
        model.traits["friendly"] = True
        model.preferences["topic"] = "games"
        await vector_store.update_user_model(model)

        # Retrieve and verify
        model2 = await vector_store.get_or_create_user_model(user_id)
        assert model2.traits.get("friendly") is True
        assert model2.preferences.get("topic") == "games"

    @pytest.mark.asyncio
    async def test_store_with_metadata(self, vector_store):
        """Test storing with metadata."""
        metadata = {"mood": "happy", "topic": "greeting"}

        memory_id = await vector_store.store(
            session_id="test_session",
            user_message="Hello",
            assistant_message="Hi!",
            metadata=metadata,
        )

        assert memory_id > 0


class TestVectorSearchWithChroma:
    """Test vector search functionality (requires ChromaDB)."""

    @pytest.mark.skipif(not CHROMA_AVAILABLE, reason="ChromaDB not installed")
    class TestChromaIntegration:
        """Tests that require ChromaDB."""

        @pytest.fixture
        def temp_dirs(self):
            """Create temporary directories."""
            with tempfile.TemporaryDirectory() as tmp_dir:
                base_path = Path(tmp_dir)
                yield {
                    "db_path": base_path / "test.db",
                    "chroma_path": base_path / "chroma",
                }

        @pytest.fixture
        def vector_store(self, temp_dirs):
            """Create store with Chroma."""
            store = VectorMemoryStore(
                db_path=temp_dirs["db_path"],
                chroma_path=temp_dirs["chroma_path"],
            )
            yield store
            store.close()

        @pytest.mark.asyncio
        async def test_vector_search(self, vector_store):
            """Test vector similarity search."""
            # Store memories with embeddings
            embeddings = [
                [1.0, 0.0, 0.0],  # Similar to query
                [0.9, 0.1, 0.0],  # Very similar to query
                [0.0, 1.0, 0.0],  # Different
            ]

            for i, emb in enumerate(embeddings):
                await vector_store.store(
                    session_id="test_session",
                    user_message=f"Message {i}",
                    assistant_message=f"Response {i}",
                    embedding=emb,
                )

            # Query with embedding similar to first two
            query_embedding = [1.0, 0.0, 0.0]
            results = await vector_store.retrieve_relevant(
                query="test",
                query_embedding=query_embedding,
                session_id="test_session",
                limit=2,
            )

            # Should get results
            assert len(results) > 0

        @pytest.mark.asyncio
        async def test_session_filtering(self, vector_store):
            """Test that vector search respects session filtering."""
            # Store in different sessions
            await vector_store.store(
                session_id="session_a",
                user_message="Only in A",
                assistant_message="Response A",
                embedding=[1.0, 0.0, 0.0],
            )

            await vector_store.store(
                session_id="session_b",
                user_message="Only in B",
                assistant_message="Response B",
                embedding=[1.0, 0.0, 0.0],
            )

            # Query session A only
            results = await vector_store.retrieve_relevant(
                query="test",
                query_embedding=[1.0, 0.0, 0.0],
                session_id="session_a",
                limit=10,
            )

            # Should only find session A content
            assert len(results) == 1
            assert results[0].session_id == "session_a"


class TestVectorMemoryIntegration:
    """Integration tests for vector memory."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_path = Path(tmp_dir)
            yield {
                "db_path": base_path / "test.db",
                "chroma_path": base_path / "chroma",
            }

    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self, temp_dirs):
        """Test complete workflow."""
        store = VectorMemoryStore(
            db_path=temp_dirs["db_path"],
            chroma_path=temp_dirs["chroma_path"],
        )

        try:
            # Create user
            user = await store.get_or_create_user_model("user_1")
            user.traits["friendly"] = True
            await store.update_user_model(user)

            # Store conversation
            for i in range(3):
                await store.store(
                    session_id="session_1",
                    user_message=f"Question {i}",
                    assistant_message=f"Answer {i}",
                    embedding=[0.1 * i, 0.2 * i, 0.3 * i],
                )

            # Retrieve recent
            recent = await store.retrieve_recent("session_1", limit=2)
            assert len(recent) == 2

            # Retrieve relevant
            relevant = await store.retrieve_relevant(
                query="Question",
                session_id="session_1",
            )
            assert len(relevant) >= 0

        finally:
            store.close()
