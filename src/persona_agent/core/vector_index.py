"""Vector-based memory index for optimized retrieval.

Provides efficient semantic search over memories using embeddings
and approximate nearest neighbor (ANN) search.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    """Protocol for embedding provider."""

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        ...


@dataclass
class VectorMemory:
    """A memory with its vector embedding."""

    id: str
    session_id: str
    user_message: str
    assistant_message: str
    embedding: list[float]
    timestamp: float
    metadata: dict[str, Any]

    def to_text(self) -> str:
        """Convert to searchable text."""
        return f"User: {self.user_message}\nAssistant: {self.assistant_message}"


class VectorMemoryIndex:
    """Vector-based memory index for semantic retrieval.

    Uses a vector store (ChromaDB, FAISS, or similar) for efficient
    similarity search over memory embeddings.
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider | None = None,
        persist_dir: Path | str | None = None,
        collection_name: str = "memories",
    ):
        """Initialize vector memory index.

        Args:
            embedding_provider: Provider for generating embeddings
            persist_dir: Directory for persisting the index
            collection_name: Name of the collection in the vector store
        """
        self.embedding_provider = embedding_provider
        self.persist_dir = Path(persist_dir) if persist_dir else None
        self.collection_name = collection_name
        self._client: Any = None
        self._collection: Any = None

    async def _ensure_initialized(self) -> bool:
        """Ensure the vector store is initialized.

        Returns:
            True if initialized successfully
        """
        if self._collection is not None:
            return True

        try:
            import chromadb

            if self.persist_dir:
                self.persist_dir.mkdir(parents=True, exist_ok=True)
                self._client = chromadb.PersistentClient(path=str(self.persist_dir))
            else:
                self._client = chromadb.Client()

            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            return True

        except ImportError:
            logger.warning("ChromaDB not installed, vector search unavailable")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            return False

    async def add_memory(
        self,
        memory_id: str,
        session_id: str,
        user_message: str,
        assistant_message: str,
        timestamp: float,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Add a memory to the index.

        Args:
            memory_id: Unique memory identifier
            session_id: Session identifier
            user_message: User's message
            assistant_message: Assistant's response
            timestamp: Memory timestamp
            metadata: Optional metadata

        Returns:
            True if added successfully
        """
        if not await self._ensure_initialized():
            return False

        if not self.embedding_provider:
            logger.warning("No embedding provider configured")
            return False

        try:
            # Generate embedding
            text = f"User: {user_message}\nAssistant: {assistant_message}"
            embedding = await self.embedding_provider.embed(text)

            # Add to collection
            self._collection.add(
                ids=[memory_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[
                    {
                        "session_id": session_id,
                        "timestamp": timestamp,
                        "user_message": user_message[:500],  # Truncate for metadata
                        "assistant_message": assistant_message[:500],
                        **(metadata or {}),
                    }
                ],
            )
            return True

        except Exception as e:
            logger.error(f"Failed to add memory to index: {e}")
            return False

    async def search(
        self,
        query: str,
        session_id: str | None = None,
        limit: int = 5,
        min_similarity: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Search for semantically similar memories.

        Args:
            query: Search query
            session_id: Optional session filter
            limit: Maximum number of results
            min_similarity: Minimum similarity score (0-1)

        Returns:
            List of matching memories with similarity scores
        """
        if not await self._ensure_initialized():
            return []

        if not self.embedding_provider:
            logger.warning("No embedding provider configured")
            return []

        try:
            # Generate query embedding
            query_embedding = await self.embedding_provider.embed(query)

            # Build filter
            where_filter = None
            if session_id:
                where_filter = {"session_id": session_id}

            # Query collection
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=limit * 2,  # Get more results for filtering
                where=where_filter,
            )

            # Format results
            memories = []
            if results["ids"] and results["ids"][0]:
                for i, memory_id in enumerate(results["ids"][0]):
                    # Convert distance to similarity (cosine distance)
                    distance = results["distances"][0][i] if results["distances"] else 0
                    similarity = 1 - distance

                    if similarity >= min_similarity:
                        metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                        memories.append(
                            {
                                "id": memory_id,
                                "similarity": similarity,
                                "session_id": metadata.get("session_id"),
                                "timestamp": metadata.get("timestamp"),
                                "user_message": metadata.get("user_message"),
                                "assistant_message": metadata.get("assistant_message"),
                            }
                        )

            # Sort by similarity and limit
            memories.sort(key=lambda x: x["similarity"], reverse=True)
            return memories[:limit]

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    async def delete_session_memories(self, session_id: str) -> bool:
        """Delete all memories for a session.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted successfully
        """
        if not await self._ensure_initialized():
            return False

        try:
            self._collection.delete(where={"session_id": session_id})
            return True
        except Exception as e:
            logger.error(f"Failed to delete session memories: {e}")
            return False

    async def get_stats(self) -> dict[str, Any]:
        """Get index statistics.

        Returns:
            Statistics dict
        """
        if not await self._ensure_initialized():
            return {"count": 0, "indexed": False}

        try:
            count = self._collection.count()
            return {
                "count": count,
                "indexed": True,
                "collection": self.collection_name,
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"count": 0, "indexed": False, "error": str(e)}


class SimpleEmbeddingProvider:
    """Simple embedding provider using sentence-transformers or similar.

    Falls back to keyword-based pseudo-embeddings if no model available.
    """

    def __init__(self, model_name: str | None = None):
        """Initialize embedding provider.

        Args:
            model_name: Name of the sentence-transformers model
        """
        self.model_name = model_name or "all-MiniLM-L6-v2"
        self._model: Any = None
        self._fallback = False

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        if self._fallback:
            return self._keyword_embedding(text)

        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name)
            except ImportError:
                logger.warning("sentence-transformers not installed, using fallback")
                self._fallback = True
                return self._keyword_embedding(text)

        try:
            import asyncio
            from concurrent.futures import ThreadPoolExecutor

            # Run in thread pool since sentence-transformers is synchronous
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as pool:
                embedding = await loop.run_in_executor(
                    pool, lambda: self._model.encode(text, convert_to_list=True)
                )
            return embedding

        except Exception as e:
            logger.warning(f"Embedding failed, using fallback: {e}")
            return self._keyword_embedding(text)

    def _keyword_embedding(self, text: str) -> list[float]:
        """Generate simple keyword-based embedding as fallback.

        This is not a real embedding but provides basic similarity
        for common keywords.
        """
        # Common keywords for basic matching
        keywords = [
            "name",
            "like",
            "love",
            "hate",
            "work",
            "job",
            "family",
            "friend",
            "home",
            "live",
            "want",
            "need",
            "feel",
            "think",
            "know",
            "learn",
            "study",
            "play",
            "game",
            "movie",
            "book",
            "food",
            "eat",
            "drink",
            "travel",
            "visit",
            "plan",
            "goal",
        ]

        text_lower = text.lower()
        embedding = [1.0 if kw in text_lower else 0.0 for kw in keywords]

        # Normalize
        magnitude = sum(x**2 for x in embedding) ** 0.5
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]

        return embedding
