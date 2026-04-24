"""Memory system for persona-agent.

Inspired by Honcho (https://github.com/plastic-labs/honcho) - user modeling
and memory system for AI agents.

Key features:
- Cross-session memory persistence
- User modeling and dialectic memory
- Vector-based semantic retrieval
- Conversation history management
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from persona_agent.core.db_encryption import FernetColumnEncryptor

logger = logging.getLogger(__name__)


@dataclass
class Memory:
    """A single memory entry."""

    id: str | None
    session_id: str
    timestamp: float
    user_message: str
    assistant_message: str
    embedding: list[float] | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class UserModel:
    """User model for dialectic memory."""

    user_id: str
    traits: dict[str, Any]
    preferences: dict[str, Any]
    relationship_stage: str
    interaction_patterns: list[dict]
    created_at: float
    updated_at: float


class MemoryStore:
    """SQLite-based memory store with vector search support.

    Inspired by Honcho's approach to user modeling and memory,
    but simplified for local deployment.
    """

    def __init__(self, db_path: Path | str = "memory/persona_agent.db"):
        """Initialize memory store.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._encryptor = FernetColumnEncryptor(os.environ.get("PERSONA_AGENT_DB_ENCRYPTION_KEY"))
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            # Conversations table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    user_message TEXT NOT NULL,
                    assistant_message TEXT NOT NULL,
                    embedding TEXT,  -- JSON array
                    metadata TEXT    -- JSON object
                )
            """)

            # User models table (Honcho-inspired)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_models (
                    user_id TEXT PRIMARY KEY,
                    traits TEXT,      -- JSON object
                    preferences TEXT, -- JSON object
                    relationship_stage TEXT,
                    interaction_patterns TEXT, -- JSON array
                    created_at REAL,
                    updated_at REAL
                )
            """)

            # Memory summaries (for long-term context)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    key_points TEXT,  -- JSON array
                    timestamp REAL NOT NULL
                )
            """)

            # Create indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_session
                ON conversations(session_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_timestamp
                ON conversations(timestamp)
            """)

            conn.commit()

    async def store(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        embedding: list[float] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Store a conversation exchange.

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

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO conversations
                (session_id, timestamp, user_message, assistant_message, embedding, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    timestamp,
                    self._encryptor.encrypt(user_message),
                    self._encryptor.encrypt(assistant_message),
                    self._encryptor.encrypt(json.dumps(embedding)) if embedding else None,
                    self._encryptor.encrypt(json.dumps(metadata)) if metadata else None,
                ),
            )
            conn.commit()

        logger.debug(f"Stored memory for session {session_id}")
        return cursor.lastrowid

    async def retrieve_recent(
        self,
        session_id: str,
        limit: int = 10,
    ) -> list[Memory]:
        """Retrieve recent conversation history.

        Args:
            session_id: Session identifier
            limit: Maximum number of exchanges to retrieve

        Returns:
            List of memory entries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM conversations
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (session_id, limit),
            )

            rows = cursor.fetchall()

        memories = []
        for row in rows:  # Keep DESC order - most recent first
            user_msg = self._encryptor.decrypt(row["user_message"])
            assistant_msg = self._encryptor.decrypt(row["assistant_message"])
            if user_msg is None or assistant_msg is None:
                continue

            embedding_raw = self._encryptor.decrypt(row["embedding"])
            metadata_raw = self._encryptor.decrypt(row["metadata"])

            memories.append(
                Memory(
                    id=str(row["id"]),
                    session_id=row["session_id"],
                    timestamp=row["timestamp"],
                    user_message=user_msg,
                    assistant_message=assistant_msg,
                    embedding=json.loads(embedding_raw) if embedding_raw is not None else None,
                    metadata=json.loads(metadata_raw) if metadata_raw is not None else None,
                )
            )

        return memories

    async def retrieve_relevant(
        self,
        query: str,
        session_id: str | None = None,
        limit: int = 5,
    ) -> list[Memory]:
        """Retrieve relevant memories based on semantic similarity.

        Note: This is a simplified version. For production, use Chroma
        or another vector database.

        Args:
            query: Search query
            session_id: Optional session filter
            limit: Maximum results

        Returns:
            List of relevant memories
        """
        # For now, do keyword-based retrieval
        # In production, this would use embeddings
        keywords = query.lower().split()

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if session_id:
                cursor = conn.execute(
                    """
                    SELECT * FROM conversations
                    WHERE session_id = ?
                    ORDER BY timestamp DESC
                    """,
                    (session_id,),
                )
            else:
                cursor = conn.execute("SELECT * FROM conversations ORDER BY timestamp DESC")

            rows = cursor.fetchall()

        # Simple keyword scoring
        scored_memories = []
        for row in rows:
            user_msg = self._encryptor.decrypt(row["user_message"]) or ""
            assistant_msg = self._encryptor.decrypt(row["assistant_message"]) or ""
            content = f"{user_msg} {assistant_msg}".lower()
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                scored_memories.append((score, row))

        # Sort by score and take top results
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        top_rows = scored_memories[:limit]

        memories: list[Memory] = []
        for _, row in top_rows:
            _user_msg = self._encryptor.decrypt(row["user_message"])
            _assistant_msg = self._encryptor.decrypt(row["assistant_message"])
            if _user_msg is None or _assistant_msg is None:
                continue

            embedding_raw = self._encryptor.decrypt(row["embedding"])
            metadata_raw = self._encryptor.decrypt(row["metadata"])

            memories.append(
                Memory(
                    id=str(row["id"]),
                    session_id=row["session_id"],
                    timestamp=row["timestamp"],
                    user_message=_user_msg,
                    assistant_message=_assistant_msg,
                    embedding=json.loads(embedding_raw) if embedding_raw is not None else None,
                    metadata=json.loads(metadata_raw) if metadata_raw is not None else None,
                )
            )
        return memories

    async def get_or_create_user_model(self, user_id: str) -> UserModel:
        """Get or create a user model.

        Args:
            user_id: Unique user identifier

        Returns:
            UserModel instance
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM user_models WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()

        if row:
            traits_raw = self._encryptor.decrypt(row["traits"])
            preferences_raw = self._encryptor.decrypt(row["preferences"])
            interaction_patterns_raw = self._encryptor.decrypt(row["interaction_patterns"])
            return UserModel(
                user_id=row["user_id"],
                traits=json.loads(traits_raw) if traits_raw is not None else {},
                preferences=json.loads(preferences_raw) if preferences_raw is not None else {},
                relationship_stage=row["relationship_stage"] or "initial",
                interaction_patterns=json.loads(interaction_patterns_raw) if interaction_patterns_raw is not None else [],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

        # Create new user model
        now = time.time()
        model = UserModel(
            user_id=user_id,
            traits={},
            preferences={},
            relationship_stage="initial",
            interaction_patterns=[],
            created_at=now,
            updated_at=now,
        )

        await self.update_user_model(model)
        return model

    async def update_user_model(self, model: UserModel) -> None:
        """Update a user model.

        Args:
            model: UserModel to update
        """
        model.updated_at = time.time()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO user_models
                (user_id, traits, preferences, relationship_stage, interaction_patterns, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model.user_id,
                    self._encryptor.encrypt(json.dumps(model.traits)),
                    self._encryptor.encrypt(json.dumps(model.preferences)),
                    model.relationship_stage,
                    self._encryptor.encrypt(json.dumps(model.interaction_patterns)),
                    model.created_at,
                    model.updated_at,
                ),
            )
            conn.commit()

        logger.debug(f"Updated user model for {model.user_id}")

    async def store_summary(
        self,
        session_id: str,
        summary: str,
        key_points: list[str],
    ) -> None:
        """Store a conversation summary.

        Args:
            session_id: Session identifier
            summary: Summary text
            key_points: Key points from the conversation
        """
        timestamp = time.time()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO memory_summaries (session_id, summary, key_points, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (
                    session_id,
                    self._encryptor.encrypt(summary),
                    self._encryptor.encrypt(json.dumps(key_points)),
                    timestamp,
                ),
            )
            conn.commit()

        logger.debug(f"Stored summary for session {session_id}")

    async def get_summaries(
        self,
        session_id: str,
        limit: int = 5,
    ) -> list[dict]:
        """Get conversation summaries for a session.

        Args:
            session_id: Session identifier
            limit: Maximum number of summaries

        Returns:
            List of summary dicts
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM memory_summaries
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (session_id, limit),
            )

            rows = cursor.fetchall()

        results = []
        for row in reversed(rows):
            key_points_raw = self._encryptor.decrypt(row["key_points"])
            results.append(
                {
                    "summary": self._encryptor.decrypt(row["summary"]),
                    "key_points": json.loads(key_points_raw) if key_points_raw is not None else [],
                    "timestamp": row["timestamp"],
                }
            )
        return results

    def close(self) -> None:
        """Close database connections."""
        # SQLite connections are context managers, nothing to close
        pass
