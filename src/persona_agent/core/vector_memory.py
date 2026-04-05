"""Vector memory store with ChromaDB for semantic search.

Implements proper vector-based memory retrieval as requested,
similar to Honcho's approach.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

try:
    import chromadb

    CHROMA_AVAILABLE = True

    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

from persona_agent.core.memory_store import MemoryStore as SQLiteMemoryStore

logger = logging.getLogger(__name__)


class VectorMemoryStore:
    """Memory store with vector search using ChromaDB.

    Extends the SQLite memory store with semantic search capabilities
    using vector embeddings.
    """

    def __init__(
        self,
        db_path: Path | str = "memory/persona_agent.db",
        chroma_path: Path | str = "memory/chroma",
    ):
        """Initialize vector memory store.

        Args:
            db_path: Path to SQLite database
            chroma_path: Path to ChromaDB directory
        """
        self.sqlite_store = SQLiteMemoryStore(db_path)
        self.chroma_path = Path(chroma_path)
        self.chroma_path.parent.mkdir(parents=True, exist_ok=True)

        if CHROMA_AVAILABLE:
            # Use PersistentClient instead of deprecated Client()
            self.chroma_client = chromadb.PersistentClient(path=str(self.chroma_path))
            self.collection = self.chroma_client.get_or_create_collection(
                name="conversations",
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("VectorMemoryStore initialized with ChromaDB")
        else:
            self.chroma_client = None
            self.collection = None
            logger.warning("ChromaDB not available, falling back to keyword search")

    async def store(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        embedding: list[float] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Store a conversation exchange with vector embedding.

        Args:
            session_id: Unique session identifier
            user_message: User's message
            assistant_message: Assistant's response
            embedding: Vector embedding (required for vector search)
            metadata: Optional metadata

        Returns:
            ID of the stored memory
        """
        # Store in SQLite
        memory_id = await self.sqlite_store.store(
            session_id=session_id,
            user_message=user_message,
            assistant_message=assistant_message,
            embedding=embedding,
            metadata=metadata,
        )

        # Store in Chroma if available and embedding provided
        if self.collection and embedding:
            doc_id = f"{session_id}_{memory_id}"
            self.collection.add(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[f"{user_message} {assistant_message}"],
                metadatas=[
                    {
                        "session_id": session_id,
                        "memory_id": memory_id,
                        "user_message": user_message,
                        "assistant_message": assistant_message,
                        **(metadata or {}),
                    }
                ],
            )
            logger.debug(f"Stored vector embedding for memory {memory_id}")

        return memory_id

    async def retrieve_recent(
        self,
        session_id: str,
        limit: int = 10,
    ) -> list:
        """Retrieve recent conversation history.

        Args:
            session_id: Session identifier
            limit: Maximum number of exchanges

        Returns:
            List of memory entries
        """
        return await self.sqlite_store.retrieve_recent(session_id, limit)

    async def retrieve_relevant(
        self,
        query: str,
        query_embedding: list[float] | None = None,
        session_id: str | None = None,
        limit: int = 5,
    ) -> list:
        """Retrieve relevant memories using vector similarity search.

        Args:
            query: Search query text
            query_embedding: Query vector embedding
            session_id: Optional session filter
            limit: Maximum results

        Returns:
            List of relevant memories
        """
        if not self.collection or not query_embedding:
            # Fall back to SQLite keyword search
            return await self.sqlite_store.retrieve_relevant(query, session_id, limit)

        # Vector search with Chroma
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit * 2,  # Get extra to filter by session
            include=["metadatas", "distances"],
        )

        from persona_agent.core.memory_store import Memory

        memories = []
        for _i, metadata in enumerate(results["metadatas"][0]):
            # Filter by session if specified
            if session_id and metadata.get("session_id") != session_id:
                continue

            memory = Memory(
                id=str(metadata.get("memory_id")),
                session_id=metadata.get("session_id"),
                timestamp=metadata.get("timestamp", time.time()),
                user_message=metadata.get("user_message"),
                assistant_message=metadata.get("assistant_message"),
                embedding=None,  # Don't return embedding to save memory
                metadata={
                    k: v
                    for k, v in metadata.items()
                    if k
                    not in [
                        "session_id",
                        "memory_id",
                        "user_message",
                        "assistant_message",
                        "timestamp",
                    ]
                },
            )
            memories.append(memory)

            if len(memories) >= limit:
                break

        return memories

    async def get_or_create_user_model(self, user_id: str):
        """Get or create a user model."""
        return await self.sqlite_store.get_or_create_user_model(user_id)

    async def update_user_model(self, model) -> None:
        """Update a user model."""
        await self.sqlite_store.update_user_model(model)

    def close(self) -> None:
        """Close all connections."""
        # PersistentClient auto-persists, only close SQLite
        self.sqlite_store.close()
