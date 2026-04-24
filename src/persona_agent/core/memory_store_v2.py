"""Enhanced memory store v2 with LLM importance scoring and vector search.

Integrates:
- LLM-based importance scoring
- Smart memory compression
- Vector-based semantic retrieval
- Multi-level memory hierarchy
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiosqlite

from persona_agent.core.importance_scorer import ImportanceScorer
from persona_agent.core.memory_compression import MemoryCompressor
from persona_agent.core.memory_store import Memory, MemoryStore
from persona_agent.core.vector_index import SimpleEmbeddingProvider, VectorMemoryIndex

if TYPE_CHECKING:
    from persona_agent.core.importance_scorer import LLMClient

logger = logging.getLogger(__name__)


@dataclass
class EnhancedMemory(Memory):
    """Memory with importance score and compression status."""

    importance_score: int = 3
    importance_level: str = "MEDIUM"
    importance_reasoning: str = ""
    is_compressed: bool = False
    compressed_from: list[str] | None = None
    compression_summary: str | None = None


class MemoryStoreV2(MemoryStore):
    """Enhanced memory store with LLM-based features.

    Extends the base MemoryStore with:
    - Automatic importance scoring
    - Vector-based semantic search
    - Smart memory compression
    """

    def __init__(
        self,
        db_path: Path | str = "memory/persona_agent.db",
        llm_client: LLMClient | None = None,
        enable_importance_scoring: bool = True,
        enable_vector_index: bool = True,
        enable_compression: bool = True,
        vector_persist_dir: Path | str | None = None,
    ):
        """Initialize enhanced memory store.

        Args:
            db_path: Path to SQLite database
            llm_client: LLM client for scoring and compression
            enable_importance_scoring: Whether to enable importance scoring
            enable_vector_index: Whether to enable vector search
            enable_compression: Whether to enable memory compression
            vector_persist_dir: Directory for vector index persistence
        """
        super().__init__(db_path)

        # Initialize components
        self.importance_scorer = ImportanceScorer(llm_client) if enable_importance_scoring else None
        self.compressor = MemoryCompressor(llm_client) if enable_compression else None

        # Vector index
        self.vector_index: VectorMemoryIndex | None = None
        if enable_vector_index:
            embedding_provider = SimpleEmbeddingProvider()
            self.vector_index = VectorMemoryIndex(
                embedding_provider=embedding_provider,
                persist_dir=vector_persist_dir or Path(db_path).parent / "vectors",
            )

        self._schema_upgraded = False

    async def _ensure_initialized(self) -> None:
        """Initialize base schema and upgrade to v2 if needed."""
        await super()._ensure_initialized()
        if not self._schema_upgraded:
            await self._upgrade_schema()

    async def _upgrade_schema(self) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            # Check if importance columns exist
            cursor = await conn.execute("PRAGMA table_info(conversations)")
            columns = {row[1] for row in await cursor.fetchall()}

            if "importance_score" not in columns:
                logger.info("Upgrading schema for importance scoring")
                await conn.execute("""
                    ALTER TABLE conversations
                    ADD COLUMN importance_score INTEGER DEFAULT 3
                """)
                await conn.execute("""
                    ALTER TABLE conversations
                    ADD COLUMN importance_level TEXT DEFAULT 'MEDIUM'
                """)
                await conn.execute("""
                    ALTER TABLE conversations
                    ADD COLUMN importance_reasoning TEXT
                """)
                await conn.execute("""
                    ALTER TABLE conversations
                    ADD COLUMN is_compressed BOOLEAN DEFAULT 0
                """)
                await conn.execute("""
                    ALTER TABLE conversations
                    ADD COLUMN compressed_from TEXT
                """)
                await conn.execute("""
                    ALTER TABLE conversations
                    ADD COLUMN compression_summary TEXT
                """)

            # Create compressed_memories table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS compressed_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    key_facts TEXT,
                    original_ids TEXT,
                    importance_range_min INTEGER,
                    importance_range_max INTEGER,
                    timestamp_start REAL,
                    timestamp_end REAL,
                    compression_ratio REAL,
                    metadata TEXT,
                    created_at REAL NOT NULL
                )
            """)

            await conn.commit()
        self._schema_upgraded = True

    async def store(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        embedding: list[float] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Store a conversation exchange with importance scoring.

        Args:
            session_id: Unique session identifier
            user_message: User's message
            assistant_message: Assistant's response
            embedding: Optional embedding vector
            metadata: Optional metadata dict

        Returns:
            ID of the stored memory
        """
        timestamp = time.time()

        # Calculate importance
        importance_data = {
            "score": 3,
            "level": "MEDIUM",
            "reasoning": "",
        }

        if self.importance_scorer:
            try:
                score = await self.importance_scorer.score_memory(user_message, assistant_message)
                importance_data = {
                    "score": score.score,
                    "level": score.level.name,
                    "reasoning": score.reasoning[:500],  # Truncate
                }
            except Exception as e:
                logger.warning(f"Importance scoring failed: {e}")

        await self._ensure_initialized()
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                """
                INSERT INTO conversations
                (session_id, timestamp, user_message, assistant_message,
                 embedding, metadata, importance_score, importance_level,
                 importance_reasoning, is_compressed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    timestamp,
                    self._encryptor.encrypt(user_message),
                    self._encryptor.encrypt(assistant_message),
                    self._encryptor.encrypt(json.dumps(embedding)) if embedding else None,
                    self._encryptor.encrypt(json.dumps(metadata)) if metadata else None,
                    importance_data["score"],
                    importance_data["level"],
                    self._encryptor.encrypt(str(importance_data["reasoning"])),
                    False,
                ),
            )
            await conn.commit()
            memory_id = cursor.lastrowid

        # Add to vector index
        if self.vector_index:
            try:
                await self.vector_index.add_memory(
                    memory_id=str(memory_id),
                    session_id=session_id,
                    user_message=user_message,
                    assistant_message=assistant_message,
                    timestamp=timestamp,
                    metadata={"importance_score": importance_data["score"]},
                )
            except Exception as e:
                logger.warning(f"Vector index update failed: {e}")

        logger.debug(
            f"Stored memory for session {session_id} with importance {importance_data['score']}"
        )
        return memory_id if memory_id is not None else -1

    async def retrieve_relevant(  # type: ignore[override]
        self,
        query: str,
        session_id: str | None = None,
        limit: int = 5,
        use_vector: bool = True,
        min_importance: int | None = None,
    ) -> list[EnhancedMemory]:
        """Retrieve relevant memories using semantic search.

        Args:
            query: Search query
            session_id: Optional session filter
            limit: Maximum results
            use_vector: Whether to use vector search (fallback to keyword if unavailable)
            min_importance: Optional minimum importance score filter

        Returns:
            List of relevant memories
        """
        # Try vector search first
        if use_vector and self.vector_index:
            try:
                results = await self.vector_index.search(
                    query=query,
                    session_id=session_id,
                    limit=limit,
                )

                if results:
                    # Fetch full memory data from database
                    memory_ids = [r["id"] for r in results]
                    memories = await self._fetch_memories_by_ids(memory_ids)

                    # Sort by vector similarity (results are already sorted)
                    id_to_memory = {m.id: m for m in memories}
                    sorted_memories = [
                        id_to_memory[r["id"]] for r in results if r["id"] in id_to_memory
                    ]

                    # Filter by importance if specified
                    if min_importance:
                        sorted_memories = [
                            m for m in sorted_memories if m.importance_score >= min_importance
                        ]

                    return sorted_memories[:limit]
            except Exception as e:
                logger.warning(f"Vector search failed, using fallback: {e}")

        # Fallback to keyword-based retrieval
        return await self._retrieve_keyword_based(query, session_id, limit, min_importance)

    async def _fetch_memories_by_ids(self, memory_ids: list[str]) -> list[EnhancedMemory]:
        """Fetch memories by their IDs."""
        if not memory_ids:
            return []

        placeholders = ",".join("?" * len(memory_ids))

        await self._ensure_initialized()
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                f"""
                SELECT * FROM conversations
                WHERE id IN ({placeholders})
                """,
                memory_ids,
            )
            rows = await cursor.fetchall()

        return [self._row_to_enhanced_memory(row) for row in rows]

    async def _retrieve_keyword_based(
        self,
        query: str,
        session_id: str | None,
        limit: int,
        min_importance: int | None,
    ) -> list[EnhancedMemory]:
        """Fallback keyword-based retrieval."""
        keywords = query.lower().split()

        await self._ensure_initialized()
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row

            where_clauses = []
            params = []

            if session_id:
                where_clauses.append("session_id = ?")
                params.append(session_id)

            if min_importance is not None:
                where_clauses.append("importance_score >= ?")
                params.append(str(min_importance))

            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            cursor = await conn.execute(
                f"""
                SELECT * FROM conversations
                {where_sql}
                ORDER BY timestamp DESC
                """,
                params,
            )
            rows = await cursor.fetchall()

        # Score by keyword matches
        scored = []
        for row in rows:
            user_msg = self._encryptor.decrypt(row["user_message"]) or ""
            assistant_msg = self._encryptor.decrypt(row["assistant_message"]) or ""
            content = f"{user_msg} {assistant_msg}".lower()
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                scored.append((score, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_rows = scored[:limit]

        return [self._row_to_enhanced_memory(row) for _, row in top_rows]

    def _row_to_enhanced_memory(self, row: aiosqlite.Row) -> EnhancedMemory:
        """Convert database row to EnhancedMemory."""
        row_dict = dict(row)
        user_msg = self._encryptor.decrypt(row["user_message"])
        assistant_msg = self._encryptor.decrypt(row["assistant_message"])
        if user_msg is None or assistant_msg is None:
            raise ValueError("user_message and assistant_message cannot be None")

        embedding_raw = self._encryptor.decrypt(row["embedding"])
        metadata_raw = self._encryptor.decrypt(row["metadata"])
        compressed_from_raw = row["compressed_from"]

        return EnhancedMemory(
            id=str(row["id"]),
            session_id=row["session_id"],
            timestamp=row["timestamp"],
            user_message=user_msg,
            assistant_message=assistant_msg,
            embedding=json.loads(embedding_raw) if embedding_raw is not None else None,
            metadata=json.loads(metadata_raw) if metadata_raw is not None else None,
            importance_score=row_dict.get("importance_score", 3),
            importance_level=row_dict.get("importance_level", "MEDIUM"),
            importance_reasoning=self._encryptor.decrypt(row["importance_reasoning"]) or "",
            is_compressed=bool(row_dict.get("is_compressed", 0)),
            compressed_from=(
                json.loads(compressed_from_raw) if compressed_from_raw is not None else None
            ),
            compression_summary=self._encryptor.decrypt(row["compression_summary"]),
        )

    async def compress_session_memories(
        self,
        session_id: str,
        target_count: int = 10,
    ) -> dict[str, Any]:
        """Compress older memories in a session.

        Args:
            session_id: Session identifier
            target_count: Target number of uncompressed memories to keep

        Returns:
            Compression statistics
        """
        if not self.compressor:
            return {"compressed": 0, "reason": "Compression not enabled"}

        # Get all memories for session
        await self._ensure_initialized()
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT * FROM conversations
                WHERE session_id = ? AND is_compressed = 0
                ORDER BY timestamp DESC
                """,
                (session_id,),
            )
            rows = list(await cursor.fetchall())

        if len(rows) <= target_count:
            return {"compressed": 0, "reason": "Not enough memories to compress"}

        # Convert to memory dicts and importance scores
        memories = []
        importance_scores = []

        for row in rows:
            row_dict = dict(row)
            memories.append(
                {
                    "id": row["id"],
                    "user_message": self._encryptor.decrypt(row["user_message"]) or "",
                    "assistant_message": self._encryptor.decrypt(row["assistant_message"]) or "",
                    "timestamp": row["timestamp"],
                    "importance_score": row_dict.get("importance_score", 3),
                }
            )

            if self.importance_scorer:
                from persona_agent.core.importance_scorer import ImportanceScore

                score_val = row_dict.get("importance_score", 3)
                importance_scores.append(
                    ImportanceScore(
                        score=score_val,
                        level=ImportanceScore.from_dict({"score": score_val}).level,
                        reasoning="",
                        category="unknown",
                        confidence=0.5,
                    )
                )

        # Select groups for compression
        groups = self.compressor.select_memories_for_compression(
            memories, importance_scores, target_count
        )

        compressed_count = 0
        for group in groups:
            if len(group) < 2:
                continue

            # Compress the group
            compressed = await self.compressor.compress_memories(group)
            if not compressed:
                continue

            # Store compressed memory
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute(
                    """
                    INSERT INTO compressed_memories
                    (session_id, summary, key_facts, original_ids,
                     importance_range_min, importance_range_max,
                     timestamp_start, timestamp_end, compression_ratio,
                     metadata, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        self._encryptor.encrypt(compressed.summary),
                        self._encryptor.encrypt(json.dumps(compressed.key_facts)),
                        json.dumps(compressed.original_ids),
                        compressed.importance_range[0],
                        compressed.importance_range[1],
                        compressed.timestamp_range[0],
                        compressed.timestamp_range[1],
                        compressed.compression_ratio,
                        self._encryptor.encrypt(json.dumps(compressed.metadata)),
                        time.time(),
                    ),
                )

                # Mark original memories as compressed
                for original_id in compressed.original_ids:
                    await conn.execute(
                        """
                        UPDATE conversations
                        SET is_compressed = 1,
                            compressed_from = ?,
                            compression_summary = ?
                        WHERE id = ?
                        """,
                        (
                            json.dumps(compressed.original_ids),
                            self._encryptor.encrypt(compressed.summary[:500]),
                            original_id,
                        ),
                    )

                await conn.commit()
                compressed_count += len(group)

        logger.info(f"Compressed {compressed_count} memories for session {session_id}")
        return {
            "compressed": compressed_count,
            "groups": len(groups),
            "remaining": len(rows) - compressed_count,
        }

    async def get_memory_stats(self, session_id: str | None = None) -> dict[str, Any]:
        """Get memory statistics.

        Args:
            session_id: Optional session filter

        Returns:
            Statistics dict
        """
        await self._ensure_initialized()
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row

            # Total memories
            if session_id:
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM conversations WHERE session_id = ?",
                    (session_id,),
                )
                row = await cursor.fetchone()
                total = row[0] if row else 0

                cursor = await conn.execute(
                    """
                    SELECT COUNT(*) FROM conversations
                    WHERE session_id = ? AND is_compressed = 1
                    """,
                    (session_id,),
                )
                row = await cursor.fetchone()
                compressed = row[0] if row else 0

                # Importance distribution
                cursor = await conn.execute(
                    """
                    SELECT importance_level, COUNT(*) as count
                    FROM conversations
                    WHERE session_id = ?
                    GROUP BY importance_level
                    """,
                    (session_id,),
                )
                importance_dist = {row["importance_level"]: row["count"] async for row in cursor}
            else:
                cursor = await conn.execute("SELECT COUNT(*) FROM conversations")
                row = await cursor.fetchone()
                total = row[0] if row else 0

                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM conversations WHERE is_compressed = 1"
                )
                row = await cursor.fetchone()
                compressed = row[0] if row else 0

                cursor = await conn.execute("""
                    SELECT importance_level, COUNT(*) as count
                    FROM conversations
                    GROUP BY importance_level
                    """)
                importance_dist = {row["importance_level"]: row["count"] async for row in cursor}

        # Vector index stats
        vector_stats = {}
        if self.vector_index:
            vector_stats = await self.vector_index.get_stats()

        return {
            "total_memories": total,
            "compressed_memories": compressed,
            "uncompressed_memories": total - compressed,
            "importance_distribution": importance_dist,
            "vector_index": vector_stats,
        }
