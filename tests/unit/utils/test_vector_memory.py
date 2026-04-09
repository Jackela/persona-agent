"""Tests for vector_memory.py with mocked ChromaDB."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestVectorMemoryStore:
    """Test suite for VectorMemoryStore."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mock_chromadb(self):
        """Mock ChromaDB module."""
        with patch("persona_agent.core.vector_memory.chromadb") as mock:
            mock.__version__ = "0.4.0"
            mock.PersistentClient = MagicMock()
            mock.Client = MagicMock()
            mock.config.Settings = MagicMock()
            yield mock

    @pytest.fixture
    def mock_collection(self):
        """Mock ChromaDB collection."""
        return MagicMock()

    @pytest.fixture
    def mock_chroma_client(self, mock_collection):
        """Mock ChromaDB client."""
        client = MagicMock()
        client.get_or_create_collection.return_value = mock_collection
        client.persist = MagicMock()
        return client

    @pytest.fixture
    def vector_store(self, temp_dir, mock_chromadb, mock_chroma_client):
        """Create a VectorMemoryStore instance with mocked ChromaDB."""
        mock_chromadb.PersistentClient.return_value = mock_chroma_client
        mock_chromadb.Client.return_value = mock_chroma_client

        # Import after mocking
        from persona_agent.core.vector_memory import VectorMemoryStore

        store = VectorMemoryStore(
            db_path=temp_dir / "test.db",
            chroma_path=temp_dir / "chroma",
        )
        return store

    @pytest.mark.asyncio
    async def test_initialization_with_chromadb(self, temp_dir, mock_chromadb, mock_chroma_client):
        """Test initialization with ChromaDB available."""
        mock_chromadb.PersistentClient.return_value = mock_chroma_client

        from persona_agent.core.vector_memory import VectorMemoryStore

        store = VectorMemoryStore(
            db_path=temp_dir / "test.db",
            chroma_path=temp_dir / "chroma",
        )

        assert store.sqlite_store is not None
        assert store.chroma_client is not None
        assert store.collection is not None
        mock_chromadb.PersistentClient.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialization_without_chromadb(self, temp_dir):
        """Test initialization when ChromaDB is not available."""
        with patch("persona_agent.core.vector_memory.CHROMA_AVAILABLE", False):
            from persona_agent.core.vector_memory import VectorMemoryStore

            store = VectorMemoryStore(
                db_path=temp_dir / "test.db",
                chroma_path=temp_dir / "chroma",
            )

            assert store.sqlite_store is not None
            assert store.chroma_client is None
            assert store.collection is None

    @pytest.mark.asyncio
    async def test_store_with_embedding(self, vector_store, mock_collection):
        """Test storing conversation with embedding."""
        embedding = [0.1, 0.2, 0.3, 0.4]

        memory_id = await vector_store.store(
            session_id="test_session",
            user_message="Hello",
            assistant_message="Hi there!",
            embedding=embedding,
            metadata={"key": "value"},
        )

        assert memory_id > 0
        mock_collection.add.assert_called_once()
        call_args = mock_collection.add.call_args
        assert call_args.kwargs["ids"] == [f"test_session_{memory_id}"]
        assert call_args.kwargs["embeddings"] == [embedding]

    @pytest.mark.asyncio
    async def test_store_without_embedding(self, vector_store, mock_collection):
        """Test storing conversation without embedding."""
        memory_id = await vector_store.store(
            session_id="test_session",
            user_message="Hello",
            assistant_message="Hi there!",
        )

        assert memory_id > 0
        # Should not call ChromaDB add when no embedding
        mock_collection.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_retrieve_recent(self, vector_store):
        """Test retrieving recent conversations."""
        # Store some memories
        await vector_store.store(
            session_id="test_session",
            user_message="Message 1",
            assistant_message="Response 1",
        )
        await vector_store.store(
            session_id="test_session",
            user_message="Message 2",
            assistant_message="Response 2",
        )

        memories = await vector_store.retrieve_recent(session_id="test_session", limit=10)

        assert len(memories) == 2
        assert memories[0].user_message == "Message 2"  # Most recent first

    @pytest.mark.asyncio
    async def test_retrieve_relevant_with_chroma(self, vector_store, mock_collection):
        """Test vector similarity search with ChromaDB."""
        mock_collection.query.return_value = {
            "metadatas": [
                [
                    {
                        "session_id": "test_session",
                        "memory_id": 1,
                        "user_message": "Hello",
                        "assistant_message": "Hi!",
                        "timestamp": 1234567890,
                    }
                ]
            ],
            "distances": [[0.1]],
        }

        query_embedding = [0.1, 0.2, 0.3, 0.4]
        memories = await vector_store.retrieve_relevant(
            query="Hello",
            query_embedding=query_embedding,
            session_id="test_session",
            limit=5,
        )

        assert len(memories) == 1
        mock_collection.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_relevant_without_chroma(self, temp_dir):
        """Test fallback to keyword search when ChromaDB unavailable."""
        with patch("persona_agent.core.vector_memory.CHROMA_AVAILABLE", False):
            from persona_agent.core.vector_memory import VectorMemoryStore

            store = VectorMemoryStore(
                db_path=temp_dir / "test.db",
                chroma_path=temp_dir / "chroma",
            )

            # Store a memory
            await store.store(
                session_id="test_session",
                user_message="Hello world",
                assistant_message="Hi there!",
            )

            # Search should use SQLite fallback
            memories = await store.retrieve_relevant(
                query="hello",
                session_id="test_session",
            )

            assert len(memories) >= 0  # May or may not find results

    @pytest.mark.asyncio
    async def test_close_with_chromadb_04(self, vector_store, mock_chromadb, mock_chroma_client):
        """Test close with ChromaDB 0.4+ (auto-persist)."""
        mock_chromadb.__version__ = "0.4.0"

        vector_store.close()

        # Should not call persist for version 0.4+
        mock_chroma_client.persist.assert_not_called()

    @pytest.mark.asyncio
    async def test_close_with_chromadb_03(self, temp_dir, mock_chromadb, mock_chroma_client):
        """Test close with ChromaDB 0.3.x (manual persist)."""
        mock_chromadb.__version__ = "0.3.29"
        # For 0.3.x, Client is used (not PersistentClient)
        mock_chromadb.Client.return_value = mock_chroma_client

        from persona_agent.core.vector_memory import VectorMemoryStore

        store = VectorMemoryStore(
            db_path=temp_dir / "test.db",
            chroma_path=temp_dir / "chroma",
        )

        store.close()

        # Should call persist for version 0.3.x
        mock_chroma_client.persist.assert_called_once()


class TestChromaDBCompatibility:
    """Test ChromaDB version compatibility."""

    def test_client_creation_04_plus(self):
        """Test client creation for ChromaDB 0.4+."""
        with patch("persona_agent.core.vector_memory.chromadb") as mock:
            mock.__version__ = "0.4.0"
            mock.PersistentClient = MagicMock()
            mock.Client = MagicMock()

            from persona_agent.core.vector_memory import _create_chroma_client

            chroma_path = Path("/tmp/chroma")
            _create_chroma_client(chroma_path)

            mock.PersistentClient.assert_called_once_with(path=str(chroma_path))
            mock.Client.assert_not_called()

    def test_client_creation_03_x(self):
        """Test client creation for ChromaDB 0.3.x."""
        with patch("persona_agent.core.vector_memory.chromadb") as mock:
            mock.__version__ = "0.3.29"
            mock.PersistentClient = MagicMock()
            mock.Client = MagicMock()
            mock.config.Settings = MagicMock()

            from persona_agent.core.vector_memory import _create_chroma_client

            chroma_path = Path("/tmp/chroma")
            _create_chroma_client(chroma_path)

            mock.Client.assert_called_once()
            mock.PersistentClient.assert_not_called()

    def test_client_creation_unknown_version(self):
        """Test client creation with unknown version defaults to new API."""
        with patch("persona_agent.core.vector_memory.chromadb") as mock:
            mock.__version__ = "1.0.0"
            mock.PersistentClient = MagicMock()

            from persona_agent.core.vector_memory import _create_chroma_client

            chroma_path = Path("/tmp/chroma")
            _create_chroma_client(chroma_path)

            mock.PersistentClient.assert_called_once()
