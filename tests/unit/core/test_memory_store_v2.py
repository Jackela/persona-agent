"""Tests for memory_store_v2 module."""

import json
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from persona_agent.core.importance_scorer import ImportanceLevel, ImportanceScore
from persona_agent.core.memory_compression import CompressedMemory
from persona_agent.core.memory_store_v2 import EnhancedMemory, MemoryStoreV2


class TestEnhancedMemory:
    """Tests for EnhancedMemory dataclass."""

    def test_basic_enhanced_memory(self):
        """Test basic EnhancedMemory creation with defaults."""
        memory = EnhancedMemory(
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
        assert memory.importance_score == 3
        assert memory.importance_level == "MEDIUM"
        assert memory.importance_reasoning == ""
        assert memory.is_compressed is False
        assert memory.compressed_from is None
        assert memory.compression_summary is None

    def test_enhanced_memory_with_all_fields(self):
        """Test EnhancedMemory with all fields set."""
        memory = EnhancedMemory(
            id="2",
            session_id="test-session",
            timestamp=1234567890.0,
            user_message="Hello",
            assistant_message="Hi!",
            embedding=[0.1, 0.2],
            metadata={"key": "value"},
            importance_score=5,
            importance_level="CRITICAL",
            importance_reasoning="Contains identity info",
            is_compressed=True,
            compressed_from=["1", "2"],
            compression_summary="Summary of previous",
        )

        assert memory.importance_score == 5
        assert memory.importance_level == "CRITICAL"
        assert memory.importance_reasoning == "Contains identity info"
        assert memory.is_compressed is True
        assert memory.compressed_from == ["1", "2"]
        assert memory.compression_summary == "Summary of previous"

    def test_enhanced_memory_inherits_from_memory(self):
        """Test that EnhancedMemory is a subclass of Memory."""
        from persona_agent.core.memory_store import Memory

        memory = EnhancedMemory(
            id="1",
            session_id="test",
            timestamp=1.0,
            user_message="Hello",
            assistant_message="Hi",
        )
        assert isinstance(memory, Memory)


class TestMemoryStoreV2Init:
    """Tests for MemoryStoreV2 initialization."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary database path."""
        return tmp_path / "test_v2.db"

    def test_initialization_creates_db(self, tmp_path):
        """Test that initialization creates the database file."""
        db_path = tmp_path / "test_v2.db"
        MemoryStoreV2(
            db_path=db_path,
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )

        assert db_path.exists()

    def test_initialization_with_defaults(self, tmp_path):
        """Test initialization with default parameters."""
        db_path = tmp_path / "test_v2.db"
        store = MemoryStoreV2(db_path=db_path)

        assert store.importance_scorer is not None
        assert store.compressor is not None
        assert store.vector_index is not None

    def test_initialization_with_all_disabled(self, tmp_path):
        """Test initialization with all features disabled."""
        db_path = tmp_path / "test_v2.db"
        store = MemoryStoreV2(
            db_path=db_path,
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )

        assert store.importance_scorer is None
        assert store.compressor is None
        assert store.vector_index is None

    def test_initialization_with_llm_client(self, tmp_path):
        """Test initialization with LLM client."""
        db_path = tmp_path / "test_v2.db"
        mock_llm = AsyncMock()

        store = MemoryStoreV2(
            db_path=db_path,
            llm_client=mock_llm,
        )

        assert store.importance_scorer is not None
        assert store.importance_scorer.llm_client is mock_llm
        assert store.compressor is not None
        assert store.compressor.llm_client is mock_llm

    def test_initialization_vector_persist_dir(self, tmp_path):
        """Test initialization with custom vector persist directory."""
        db_path = tmp_path / "test_v2.db"
        vector_dir = tmp_path / "custom_vectors"

        store = MemoryStoreV2(
            db_path=db_path,
            enable_importance_scoring=False,
            enable_compression=False,
            vector_persist_dir=vector_dir,
        )

        assert store.vector_index is not None
        assert store.vector_index.persist_dir == vector_dir

    @pytest.mark.asyncio
    async def test_upgrade_schema_adds_columns(self, tmp_path):
        """Test that schema upgrade adds v2 columns."""
        db_path = tmp_path / "test_v2.db"

        # First create a base MemoryStore to get the base schema
        from persona_agent.core.memory_store import MemoryStore

        base_store = MemoryStore(db_path=db_path)
        await base_store._ensure_initialized()
        base_store.close()

        # Now initialize MemoryStoreV2 which should upgrade the schema
        store = MemoryStoreV2(
            db_path=db_path,
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )
        await store._ensure_initialized()

        # Verify columns were added
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("PRAGMA table_info(conversations)")
            columns = {row[1] for row in cursor.fetchall()}

        assert "importance_score" in columns
        assert "importance_level" in columns
        assert "importance_reasoning" in columns
        assert "is_compressed" in columns
        assert "compressed_from" in columns
        assert "compression_summary" in columns

    @pytest.mark.asyncio
    async def test_upgrade_schema_creates_compressed_memories_table(self, tmp_path):
        """Test that schema upgrade creates compressed_memories table."""
        db_path = tmp_path / "test_v2.db"

        store = MemoryStoreV2(
            db_path=db_path,
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )
        await store._ensure_initialized()

        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}

        assert "compressed_memories" in tables

    @pytest.mark.asyncio
    async def test_upgrade_schema_idempotent(self, tmp_path):
        """Test that schema upgrade is idempotent (can run multiple times)."""
        db_path = tmp_path / "test_v2.db"

        # First initialization
        store1 = MemoryStoreV2(
            db_path=db_path,
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )
        await store1._ensure_initialized()

        # Second initialization should not raise
        store2 = MemoryStoreV2(
            db_path=db_path,
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )
        await store2._ensure_initialized()

        # Should succeed without errors
        assert store2 is not None


class TestMemoryStoreV2Store:
    """Tests for MemoryStoreV2.store method."""

    @pytest.fixture
    def store_no_features(self, tmp_path):
        """Create a MemoryStoreV2 with all features disabled."""
        return MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )

    @pytest.fixture
    def store_with_scorer(self, tmp_path):
        """Create a MemoryStoreV2 with mocked importance scorer."""
        mock_llm = AsyncMock()
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            llm_client=mock_llm,
            enable_vector_index=False,
            enable_compression=False,
        )
        return store

    @pytest.mark.asyncio
    async def test_store_basic(self, store_no_features):
        """Test basic store operation."""
        memory_id = await store_no_features.store(
            session_id="test-session",
            user_message="Hello",
            assistant_message="Hi there!",
        )

        assert memory_id > 0

    @pytest.mark.asyncio
    async def test_store_with_embedding_and_metadata(self, store_no_features):
        """Test storing with embedding and metadata."""
        embedding = [0.1, 0.2, 0.3]
        metadata = {"source": "test"}

        memory_id = await store_no_features.store(
            session_id="test-session",
            user_message="Hello",
            assistant_message="Hi!",
            embedding=embedding,
            metadata=metadata,
        )

        assert memory_id > 0

        # Verify by retrieving
        memories = await store_no_features.retrieve_recent("test-session", limit=1)
        assert len(memories) == 1
        assert memories[0].embedding == embedding
        assert memories[0].metadata == metadata

    @pytest.mark.asyncio
    async def test_store_with_importance_scoring(self, store_with_scorer):
        """Test storing with importance scoring."""
        score = ImportanceScore(
            score=5,
            level=ImportanceLevel.CRITICAL,
            reasoning="Identity information",
            category="identity",
            confidence=0.9,
        )

        with patch.object(
            store_with_scorer.importance_scorer,
            "score_memory",
            return_value=score,
        ):
            memory_id = await store_with_scorer.store(
                session_id="test-session",
                user_message="My name is John",
                assistant_message="Nice to meet you, John!",
            )

        assert memory_id > 0

        with sqlite3.connect(store_with_scorer.db_path) as conn:
            cursor = conn.execute(
                "SELECT importance_score, importance_level FROM conversations WHERE id = ?",
                (memory_id,),
            )
            row = cursor.fetchone()

        assert row[0] == 5
        assert row[1] == "CRITICAL"

    @pytest.mark.asyncio
    async def test_store_importance_scoring_failure(self, store_with_scorer):
        """Test that store succeeds even if importance scoring fails."""
        with patch.object(
            store_with_scorer.importance_scorer,
            "score_memory",
            side_effect=Exception("LLM error"),
        ):
            memory_id = await store_with_scorer.store(
                session_id="test-session",
                user_message="Hello",
                assistant_message="Hi!",
            )

        assert memory_id > 0

        with sqlite3.connect(store_with_scorer.db_path) as conn:
            cursor = conn.execute(
                "SELECT importance_score, importance_level FROM conversations WHERE id = ?",
                (memory_id,),
            )
            row = cursor.fetchone()

        assert row[0] == 3
        assert row[1] == "MEDIUM"

    @pytest.mark.asyncio
    async def test_store_with_vector_index(self, tmp_path):
        """Test storing with vector index enabled."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_compression=False,
            enable_vector_index=True,
        )

        # Mock the vector index
        store.vector_index = AsyncMock()
        store.vector_index.add_memory = AsyncMock(return_value=True)

        memory_id = await store.store(
            session_id="test-session",
            user_message="Hello",
            assistant_message="Hi!",
        )

        assert memory_id > 0
        store.vector_index.add_memory.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_vector_index_failure(self, tmp_path):
        """Test that store succeeds even if vector index fails."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_compression=False,
            enable_vector_index=True,
        )

        # Mock the vector index to fail
        store.vector_index = AsyncMock()
        store.vector_index.add_memory = AsyncMock(side_effect=Exception("Vector error"))

        memory_id = await store.store(
            session_id="test-session",
            user_message="Hello",
            assistant_message="Hi!",
        )

        assert memory_id > 0

    @pytest.mark.asyncio
    async def test_store_returns_negative_one_on_failure(self, tmp_path):
        """Test that store returns -1 when lastrowid is None."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )

        # Mock the cursor to return None for lastrowid
        with patch("aiosqlite.connect") as mock_connect:
            mock_cursor = AsyncMock()
            mock_cursor.lastrowid = None
            mock_conn = AsyncMock()
            mock_conn.execute.return_value = mock_cursor
            mock_connect.return_value.__aenter__.return_value = mock_conn

            # Need to also mock the actual db_path since we're bypassing sqlite3
            store.db_path = tmp_path / "mock.db"
            result = await store.store(
                session_id="test",
                user_message="Hello",
                assistant_message="Hi!",
            )
            assert result == -1


class TestMemoryStoreV2RetrieveRelevant:
    """Tests for MemoryStoreV2.retrieve_relevant method."""

    @pytest.fixture
    async def store_with_data(self, tmp_path):
        """Create a store with test data."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )

        # Store some test data
        await store.store(
            session_id="test-session",
            user_message="I love programming in Python",
            assistant_message="That's great! Python is versatile.",
        )
        await store.store(
            session_id="test-session",
            user_message="The weather is nice today",
            assistant_message="Indeed! Perfect for a walk.",
        )
        await store.store(
            session_id="other-session",
            user_message="I enjoy JavaScript too",
            assistant_message="JavaScript is popular for web dev.",
        )

        return store

    @pytest.mark.asyncio
    async def test_retrieve_relevant_keyword_fallback(self, tmp_path):
        """Test keyword-based fallback retrieval."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )

        await store.store(
            session_id="test-session",
            user_message="I love programming in Python",
            assistant_message="That's great!",
        )
        await store.store(
            session_id="test-session",
            user_message="The weather is nice",
            assistant_message="Indeed!",
        )

        results = await store.retrieve_relevant(
            query="python programming",
            session_id="test-session",
            limit=5,
        )

        assert len(results) >= 1
        assert all(isinstance(r, EnhancedMemory) for r in results)

    @pytest.mark.asyncio
    async def test_retrieve_relevant_with_vector_search(self, tmp_path):
        """Test vector search retrieval."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=True,
            enable_compression=False,
        )

        # Mock vector index
        store.vector_index = AsyncMock()
        store.vector_index.search = AsyncMock(
            return_value=[
                {
                    "id": "1",
                    "similarity": 0.9,
                    "session_id": "test-session",
                }
            ]
        )

        # Store a memory first
        await store.store(
            session_id="test-session",
            user_message="Python is great",
            assistant_message="Yes it is!",
        )

        await store.retrieve_relevant(
            query="python",
            session_id="test-session",
            use_vector=True,
        )

        store.vector_index.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_relevant_vector_search_no_results(self, tmp_path):
        """Test vector search with no results falls back to keyword."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=True,
            enable_compression=False,
        )

        # Mock vector index to return empty results
        store.vector_index = AsyncMock()
        store.vector_index.search = AsyncMock(return_value=[])

        await store.store(
            session_id="test-session",
            user_message="Python is great",
            assistant_message="Yes!",
        )

        results = await store.retrieve_relevant(
            query="python",
            session_id="test-session",
            use_vector=True,
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_retrieve_relevant_vector_search_failure(self, tmp_path):
        """Test that vector search failure falls back to keyword search."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=True,
            enable_compression=False,
        )

        # Mock vector index to raise exception
        store.vector_index = AsyncMock()
        store.vector_index.search = AsyncMock(side_effect=Exception("Vector search error"))

        await store.store(
            session_id="test-session",
            user_message="Python is great",
            assistant_message="Yes!",
        )

        results = await store.retrieve_relevant(
            query="python",
            session_id="test-session",
            use_vector=True,
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_retrieve_relevant_no_vector_index(self, tmp_path):
        """Test retrieval when vector index is disabled."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )

        await store.store(
            session_id="test-session",
            user_message="Python is great",
            assistant_message="Yes!",
        )

        results = await store.retrieve_relevant(
            query="python",
            session_id="test-session",
            use_vector=True,  # Should still work even if vector is disabled
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_retrieve_relevant_with_min_importance(self, tmp_path):
        """Test retrieval with minimum importance filter."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )

        await store.store(
            session_id="test-session",
            user_message="Python is great",
            assistant_message="Yes!",
        )

        # Mock vector index
        store.vector_index = AsyncMock()
        store.vector_index.search = AsyncMock(
            return_value=[{"id": "1", "similarity": 0.9}]
        )

        results = await store.retrieve_relevant(
            query="python",
            session_id="test-session",
            use_vector=True,
            min_importance=4,
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_retrieve_relevant_no_session(self, tmp_path):
        """Test retrieval across all sessions."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )

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

        results = await store.retrieve_relevant(
            query="programming",
            limit=5,
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_retrieve_relevant_empty_store(self, tmp_path):
        """Test retrieval from empty store."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )

        results = await store.retrieve_relevant(
            query="python",
            session_id="test-session",
        )

        assert results == []


class TestMemoryStoreV2FetchMemoriesByIds:
    """Tests for _fetch_memories_by_ids method."""

    @pytest.mark.asyncio
    async def test_fetch_memories_by_ids(self, tmp_path):
        """Test fetching memories by IDs."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )

        # Store memories
        id1 = await store.store(
            session_id="test-session",
            user_message="Message 1",
            assistant_message="Response 1",
        )
        id2 = await store.store(
            session_id="test-session",
            user_message="Message 2",
            assistant_message="Response 2",
        )

        # Fetch by IDs
        memories = await store._fetch_memories_by_ids([str(id1), str(id2)])

        assert len(memories) == 2
        assert all(isinstance(m, EnhancedMemory) for m in memories)
        messages = {m.user_message for m in memories}
        assert "Message 1" in messages
        assert "Message 2" in messages

    @pytest.mark.asyncio
    async def test_fetch_memories_by_ids_empty(self, tmp_path):
        """Test fetching with empty ID list."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )

        memories = await store._fetch_memories_by_ids([])

        assert memories == []

    @pytest.mark.asyncio
    async def test_fetch_memories_by_ids_nonexistent(self, tmp_path):
        """Test fetching non-existent IDs."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )

        memories = await store._fetch_memories_by_ids(["99999", "88888"])

        assert memories == []


class TestMemoryStoreV2RowToEnhancedMemory:
    """Tests for _row_to_enhanced_memory method."""

    @pytest.mark.asyncio
    async def test_row_to_enhanced_memory(self, tmp_path):
        """Test converting a database row to EnhancedMemory."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )

        # Store and retrieve raw row
        await store.store(
            session_id="test-session",
            user_message="Hello",
            assistant_message="Hi!",
            embedding=[0.1, 0.2],
            metadata={"key": "value"},
        )

        with sqlite3.connect(store.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM conversations LIMIT 1")
            row = cursor.fetchone()

        memory = store._row_to_enhanced_memory(row)

        assert isinstance(memory, EnhancedMemory)
        assert memory.user_message == "Hello"
        assert memory.assistant_message == "Hi!"
        assert memory.embedding == [0.1, 0.2]
        assert memory.metadata == {"key": "value"}
        assert memory.importance_score == 3
        assert memory.importance_level == "MEDIUM"

    @pytest.mark.asyncio
    async def test_row_to_enhanced_memory_with_compression(self, tmp_path):
        """Test converting a row with compression data."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )
        await store._ensure_initialized()

        # Insert a row with compression data directly
        with sqlite3.connect(store.db_path) as conn:
            conn.execute(
                """
                INSERT INTO conversations
                (session_id, timestamp, user_message, assistant_message,
                 embedding, metadata, importance_score, importance_level,
                 importance_reasoning, is_compressed, compressed_from, compression_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "test-session",
                    1234567890.0,
                    store._encryptor.encrypt("Hello"),
                    store._encryptor.encrypt("Hi!"),
                    None,
                    None,
                    5,
                    "CRITICAL",
                    store._encryptor.encrypt("Important"),
                    1,
                    json.dumps(["1", "2"]),
                    store._encryptor.encrypt("Summary"),
                ),
            )
            conn.commit()

        with sqlite3.connect(store.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM conversations LIMIT 1")
            row = cursor.fetchone()

        memory = store._row_to_enhanced_memory(row)

        assert memory.importance_score == 5
        assert memory.importance_level == "CRITICAL"
        assert memory.importance_reasoning == "Important"
        assert memory.is_compressed is True
        assert memory.compressed_from == ["1", "2"]
        assert memory.compression_summary == "Summary"

    @pytest.mark.asyncio
    async def test_row_to_enhanced_memory_none_messages_raises(self, tmp_path):
        """Test that None messages raise ValueError."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )

        # Create a mock row with None messages
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "id": 1,
            "session_id": "test",
            "timestamp": 1.0,
            "user_message": None,
            "assistant_message": None,
            "embedding": None,
            "metadata": None,
            "importance_score": 3,
            "importance_level": "MEDIUM",
            "importance_reasoning": None,
            "is_compressed": 0,
            "compressed_from": None,
            "compression_summary": None,
        }.get(key)
        mock_row.keys = lambda: [
            "id", "session_id", "timestamp", "user_message", "assistant_message",
            "embedding", "metadata", "importance_score", "importance_level",
            "importance_reasoning", "is_compressed", "compressed_from", "compression_summary",
        ]

        # Need to make it behave like sqlite3.Row for dict() conversion
        with patch.object(store._encryptor, "decrypt", return_value=None):
            with pytest.raises(ValueError, match="cannot be None"):
                store._row_to_enhanced_memory(mock_row)


class TestMemoryStoreV2CompressSessionMemories:
    """Tests for compress_session_memories method."""

    @pytest.mark.asyncio
    async def test_compress_not_enabled(self, tmp_path):
        """Test compression when compressor is disabled."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )

        result = await store.compress_session_memories("test-session")

        assert result["compressed"] == 0
        assert result["reason"] == "Compression not enabled"

    @pytest.mark.asyncio
    async def test_compress_not_enough_memories(self, tmp_path):
        """Test compression with too few memories."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=True,
        )

        # Mock the compressor
        store.compressor = MagicMock()

        # Store only 2 memories, target is 10
        await store.store(
            session_id="test-session",
            user_message="Hello",
            assistant_message="Hi!",
        )
        await store.store(
            session_id="test-session",
            user_message="How are you?",
            assistant_message="I'm good!",
        )

        result = await store.compress_session_memories("test-session", target_count=10)

        assert result["compressed"] == 0
        assert result["reason"] == "Not enough memories to compress"

    @pytest.mark.asyncio
    async def test_compress_success(self, tmp_path):
        """Test successful compression."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=True,
        )

        # Mock the compressor
        compressed_memory = CompressedMemory(
            original_ids=["1", "2"],
            summary="Summary",
            key_facts=["Fact 1"],
            importance_range=(3, 4),
            timestamp_range=(1.0, 2.0),
            compression_ratio=2.0,
            metadata={},
        )

        store.compressor = MagicMock()
        store.compressor.select_memories_for_compression = MagicMock(
            return_value=[[{"id": 1}, {"id": 2}]]
        )
        store.compressor.compress_memories = AsyncMock(return_value=compressed_memory)

        # Store multiple memories
        for i in range(5):
            await store.store(
                session_id="test-session",
                user_message=f"Message {i}",
                assistant_message=f"Response {i}",
            )

        result = await store.compress_session_memories("test-session", target_count=2)

        assert result["compressed"] == 2
        assert result["groups"] == 1

    @pytest.mark.asyncio
    async def test_compress_empty_group_skipped(self, tmp_path):
        """Test that groups with < 2 memories are skipped."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=True,
        )

        # Mock the compressor to return a group with only 1 memory
        store.compressor = MagicMock()
        store.compressor.select_memories_for_compression = MagicMock(
            return_value=[[{"id": 1}]]  # Single memory group should be skipped
        )

        # Store multiple memories
        for i in range(5):
            await store.store(
                session_id="test-session",
                user_message=f"Message {i}",
                assistant_message=f"Response {i}",
            )

        result = await store.compress_session_memories("test-session", target_count=2)

        # Should skip the single-memory group
        assert result["compressed"] == 0

    @pytest.mark.asyncio
    async def test_compress_with_importance_scorer(self, tmp_path):
        """Test compression with importance scorer."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=True,
            enable_vector_index=False,
            enable_compression=True,
        )

        # Mock importance scorer
        store.importance_scorer = MagicMock()

        compressed_memory = CompressedMemory(
            original_ids=["1", "2"],
            summary="Summary",
            key_facts=["Fact 1"],
            importance_range=(3, 4),
            timestamp_range=(1.0, 2.0),
            compression_ratio=2.0,
            metadata={},
        )

        store.compressor = MagicMock()
        store.compressor.select_memories_for_compression = MagicMock(
            return_value=[[{"id": 1}, {"id": 2}]]
        )
        store.compressor.compress_memories = AsyncMock(return_value=compressed_memory)

        # Store memories
        for i in range(5):
            await store.store(
                session_id="test-session",
                user_message=f"Message {i}",
                assistant_message=f"Response {i}",
            )

        result = await store.compress_session_memories("test-session", target_count=2)

        assert result["compressed"] == 2

    @pytest.mark.asyncio
    async def test_compress_compression_returns_none(self, tmp_path):
        """Test when compressor returns None."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=True,
        )

        store.compressor = MagicMock()
        store.compressor.select_memories_for_compression = MagicMock(
            return_value=[[{"id": 1}, {"id": 2}]]
        )
        store.compressor.compress_memories = AsyncMock(return_value=None)

        # Store memories
        for i in range(5):
            await store.store(
                session_id="test-session",
                user_message=f"Message {i}",
                assistant_message=f"Response {i}",
            )

        result = await store.compress_session_memories("test-session", target_count=2)

        assert result["compressed"] == 0


class TestMemoryStoreV2GetMemoryStats:
    """Tests for get_memory_stats method."""

    @pytest.mark.asyncio
    async def test_get_memory_stats_empty(self, tmp_path):
        """Test stats for empty store."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )

        stats = await store.get_memory_stats()

        assert stats["total_memories"] == 0
        assert stats["compressed_memories"] == 0
        assert stats["uncompressed_memories"] == 0
        assert stats["importance_distribution"] == {}

    @pytest.mark.asyncio
    async def test_get_memory_stats_with_data(self, tmp_path):
        """Test stats with data."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )

        # Store some memories
        await store.store(
            session_id="test-session",
            user_message="Hello",
            assistant_message="Hi!",
        )
        await store.store(
            session_id="test-session",
            user_message="How are you?",
            assistant_message="Good!",
        )

        stats = await store.get_memory_stats()

        assert stats["total_memories"] == 2
        assert stats["compressed_memories"] == 0
        assert stats["uncompressed_memories"] == 2

    @pytest.mark.asyncio
    async def test_get_memory_stats_with_session_filter(self, tmp_path):
        """Test stats filtered by session."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )

        await store.store(
            session_id="session1",
            user_message="Hello",
            assistant_message="Hi!",
        )
        await store.store(
            session_id="session2",
            user_message="How are you?",
            assistant_message="Good!",
        )

        stats = await store.get_memory_stats(session_id="session1")

        assert stats["total_memories"] == 1
        assert stats["uncompressed_memories"] == 1

    @pytest.mark.asyncio
    async def test_get_memory_stats_with_vector_index(self, tmp_path):
        """Test stats with vector index."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=True,
            enable_compression=False,
        )

        # Mock vector index
        store.vector_index = AsyncMock()
        store.vector_index.get_stats = AsyncMock(return_value={"count": 5, "indexed": True})

        stats = await store.get_memory_stats()

        assert stats["vector_index"] == {"count": 5, "indexed": True}

    @pytest.mark.asyncio
    async def test_get_memory_stats_importance_distribution(self, tmp_path):
        """Test importance distribution in stats."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )
        await store._ensure_initialized()

        # Store memories with different importance levels (via direct SQL for control)
        with sqlite3.connect(store.db_path) as conn:
            for i in range(3):
                conn.execute(
                    """
                    INSERT INTO conversations
                    (session_id, timestamp, user_message, assistant_message,
                     importance_score, importance_level)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "test-session",
                        float(i),
                        store._encryptor.encrypt(f"Message {i}"),
                        store._encryptor.encrypt(f"Response {i}"),
                        i + 1,
                        ["LOW", "MEDIUM", "HIGH"][i],
                    ),
                )
            conn.commit()

        stats = await store.get_memory_stats()

        assert "LOW" in stats["importance_distribution"]
        assert "MEDIUM" in stats["importance_distribution"]
        assert "HIGH" in stats["importance_distribution"]
        assert stats["importance_distribution"]["LOW"] == 1
        assert stats["importance_distribution"]["MEDIUM"] == 1
        assert stats["importance_distribution"]["HIGH"] == 1


class TestMemoryStoreV2RetrieveKeywordBased:
    """Tests for _retrieve_keyword_based method."""

    @pytest.mark.asyncio
    async def test_retrieve_keyword_based_with_session(self, tmp_path):
        """Test keyword retrieval with session filter."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )

        await store.store(
            session_id="test-session",
            user_message="I love Python",
            assistant_message="Great!",
        )
        await store.store(
            session_id="other-session",
            user_message="I love JavaScript",
            assistant_message="Nice!",
        )

        results = await store._retrieve_keyword_based(
            query="python",
            session_id="test-session",
            limit=5,
            min_importance=None,
        )

        assert len(results) == 1
        assert results[0].user_message == "I love Python"

    @pytest.mark.asyncio
    async def test_retrieve_keyword_based_with_min_importance(self, tmp_path):
        """Test keyword retrieval with min importance filter."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )
        await store._ensure_initialized()

        # Insert with specific importance scores
        with sqlite3.connect(store.db_path) as conn:
            conn.execute(
                """
                INSERT INTO conversations
                (session_id, timestamp, user_message, assistant_message, importance_score)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "test-session",
                    1.0,
                    store._encryptor.encrypt("Python is great"),
                    store._encryptor.encrypt("Yes!"),
                    5,
                ),
            )
            conn.execute(
                """
                INSERT INTO conversations
                (session_id, timestamp, user_message, assistant_message, importance_score)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "test-session",
                    2.0,
                    store._encryptor.encrypt("Python is easy"),
                    store._encryptor.encrypt("Indeed!"),
                    2,
                ),
            )
            conn.commit()

        results = await store._retrieve_keyword_based(
            query="python",
            session_id="test-session",
            limit=5,
            min_importance=4,
        )

        assert len(results) == 1
        assert results[0].importance_score == 5

    @pytest.mark.asyncio
    async def test_retrieve_keyword_based_no_matches(self, tmp_path):
        """Test keyword retrieval with no matches."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )

        await store.store(
            session_id="test-session",
            user_message="Hello",
            assistant_message="Hi!",
        )

        results = await store._retrieve_keyword_based(
            query="nonexistent",
            session_id="test-session",
            limit=5,
            min_importance=None,
        )

        assert results == []


class TestMemoryStoreV2EdgeCases:
    """Edge case tests for MemoryStoreV2."""

    @pytest.mark.asyncio
    async def test_store_unicode(self, tmp_path):
        """Test storing unicode messages."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )

        memory_id = await store.store(
            session_id="test",
            user_message="Hello 世界 🌍",
            assistant_message="你好! 👋",
        )

        assert memory_id > 0

        memories = await store.retrieve_recent("test")
        assert memories[0].user_message == "Hello 世界 🌍"
        assert memories[0].assistant_message == "你好! 👋"

    @pytest.mark.asyncio
    async def test_store_empty_message(self, tmp_path):
        """Test storing empty messages."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )

        memory_id = await store.store(
            session_id="test",
            user_message="",
            assistant_message="",
        )

        assert memory_id > 0

    @pytest.mark.asyncio
    async def test_concurrent_sessions(self, tmp_path):
        """Test storing to multiple sessions."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )

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

    @pytest.mark.asyncio
    async def test_retrieve_recent_inherited(self, tmp_path):
        """Test that retrieve_recent from parent class still works."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            enable_importance_scoring=False,
            enable_vector_index=False,
            enable_compression=False,
        )

        for i in range(3):
            await store.store(
                session_id="test-session",
                user_message=f"Message {i}",
                assistant_message=f"Response {i}",
            )

        memories = await store.retrieve_recent("test-session", limit=2)

        assert len(memories) == 2
        # Most recent first
        assert memories[0].user_message == "Message 2"
        assert memories[1].user_message == "Message 1"

    @pytest.mark.asyncio
    async def test_importance_scorer_with_none_llm(self, tmp_path):
        """Test importance scorer when LLM client is None."""
        store = MemoryStoreV2(
            db_path=tmp_path / "test_v2.db",
            llm_client=None,
            enable_importance_scoring=True,
            enable_vector_index=False,
            enable_compression=False,
        )

        # Should use heuristic scoring
        memory_id = await store.store(
            session_id="test",
            user_message="My name is John",
            assistant_message="Nice to meet you!",
        )

        assert memory_id > 0

        with sqlite3.connect(store.db_path) as conn:
            cursor = conn.execute(
                "SELECT importance_score, importance_level FROM conversations WHERE id = ?",
                (memory_id,),
            )
            row = cursor.fetchone()

        # Heuristic scoring should detect identity pattern
        assert row[0] == 5
        assert row[1] == "CRITICAL"
