"""Session repository implementation using SQLite.

This module provides a concrete implementation of the BaseRepository
for Session entities using SQLite as the backing store.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from persona_agent.repositories.base import (
    BaseRepository,
    ConnectionError,
    EntityNotFoundError,
    PaginatedResult,
    PaginationParams,
    RepositoryError,
)
from persona_agent.repositories.models import Session


class SessionRepository(BaseRepository[Session, str]):
    """SQLite-based repository for Session entities.

    This repository stores session data in a SQLite database, including
    session metadata and associated messages.

    Attributes:
        db_path: Path to the SQLite database file
        _connection: Active SQLite connection
    """

    def __init__(self, db_path: str | Path = "memory/chat_history.db") -> None:
        """Initialize the session repository.

        Args:
            db_path: Path to the SQLite database file
        """
        super().__init__()
        self.db_path = Path(db_path)
        self._connection: sqlite3.Connection | None = None

    async def connect(self) -> None:
        """Establish connection to the SQLite database.

        Creates the database directory and initializes the schema if needed.

        Raises:
            ConnectionError: If the connection cannot be established
        """
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(self.db_path)
            self._connection.row_factory = sqlite3.Row
            self._initialize_schema()
            self._connected = True
        except sqlite3.Error as e:
            raise ConnectionError(f"Failed to connect to database: {e}")

    async def disconnect(self) -> None:
        """Close connection to the SQLite database.

        Safely closes the database connection and releases resources.
        """
        if self._connection:
            self._connection.close()
            self._connection = None
        self._connected = False

    async def is_connected(self) -> bool:
        """Check if the repository is connected to the database.

        Returns:
            True if connected, False otherwise
        """
        return self._connected and self._connection is not None

    def _initialize_schema(self) -> None:
        """Initialize the database schema.

        Creates the required tables if they do not exist.
        """
        if not self._connection:
            return

        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                last_activity TIMESTAMP NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_last_activity
                ON sessions(last_activity DESC);

            CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id);
            """
        )
        self._connection.commit()

    async def create(self, entity: Session) -> Session:
        """Create a new session in the repository.

        Args:
            entity: The session to create

        Returns:
            The created session

        Raises:
            DuplicateEntityError: If a session with the same ID already exists
            ConnectionError: If not connected to the database
        """
        if not self._connection:
            raise ConnectionError("Not connected to database")

        try:
            self._connection.execute(
                "INSERT INTO sessions (session_id, last_activity) VALUES (?, ?)",
                (entity.session_id, entity.last_activity.timestamp()),
            )

            for msg in entity.messages:
                self._connection.execute(
                    """INSERT INTO messages (session_id, role, content, timestamp)
                       VALUES (?, ?, ?, ?)""",
                    (
                        entity.session_id,
                        msg.get("role", "user"),
                        msg.get("content", ""),
                        msg.get("timestamp", datetime.now().timestamp()),
                    ),
                )

            self._connection.commit()
            return entity
        except sqlite3.IntegrityError as e:
            from persona_agent.repositories.base import DuplicateEntityError

            raise DuplicateEntityError("Session", entity.session_id)
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to create session: {e}")

    async def get_by_id(self, entity_id: str) -> Session | None:
        """Retrieve a session by its identifier.

        Args:
            entity_id: The unique identifier of the session

        Returns:
            The session if found, None otherwise

        Raises:
            ConnectionError: If not connected to the database
        """
        if not self._connection:
            raise ConnectionError("Not connected to database")

        cursor = self._connection.execute(
            "SELECT session_id, last_activity FROM sessions WHERE session_id = ?",
            (entity_id,),
        )
        row = cursor.fetchone()

        if not row:
            return None

        messages = await self._get_messages(entity_id)

        return Session(
            session_id=row["session_id"],
            messages=messages,
            last_activity=datetime.fromtimestamp(row["last_activity"]),
        )

    async def _get_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Get all messages for a session.

        Args:
            session_id: The session identifier

        Returns:
            List of messages
        """
        if not self._connection:
            return []

        cursor = self._connection.execute(
            """SELECT role, content, timestamp FROM messages
               WHERE session_id = ? ORDER BY timestamp""",
            (session_id,),
        )

        return [
            {
                "role": row["role"],
                "content": row["content"],
                "timestamp": row["timestamp"],
            }
            for row in cursor.fetchall()
        ]

    async def update(self, entity: Session) -> Session:
        """Update an existing session.

        Uses an append-only strategy for messages to avoid N+1 deletes/inserts.
        Only new messages (those not yet in the database) are inserted.

        Args:
            entity: The session to update

        Returns:
            The updated session

        Raises:
            EntityNotFoundError: If the session does not exist
            ConnectionError: If not connected to the database
        """
        if not self._connection:
            raise ConnectionError("Not connected to database")

        cursor = self._connection.execute(
            "SELECT 1 FROM sessions WHERE session_id = ?",
            (entity.session_id,),
        )
        if not cursor.fetchone():
            raise EntityNotFoundError("Session", entity.session_id)

        try:
            self._connection.execute(
                "UPDATE sessions SET last_activity = ? WHERE session_id = ?",
                (entity.last_activity.timestamp(), entity.session_id),
            )

            cursor = self._connection.execute(
                "SELECT COUNT(*) as count FROM messages WHERE session_id = ?",
                (entity.session_id,),
            )
            existing_count = cursor.fetchone()["count"]

            new_messages = entity.messages[existing_count:]
            for msg in new_messages:
                self._connection.execute(
                    """INSERT INTO messages (session_id, role, content, timestamp)
                       VALUES (?, ?, ?, ?)""",
                    (
                        entity.session_id,
                        msg.get("role", "user"),
                        msg.get("content", ""),
                        msg.get("timestamp", datetime.now().timestamp()),
                    ),
                )

            self._connection.commit()
            return entity
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to update session: {e}")

    async def delete(self, entity_id: str) -> bool:
        """Delete a session by its identifier.

        Args:
            entity_id: The unique identifier of the session to delete

        Returns:
            True if the session was deleted, False if it didn't exist

        Raises:
            ConnectionError: If not connected to the database
        """
        if not self._connection:
            raise ConnectionError("Not connected to database")

        try:
            cursor = self._connection.execute(
                "DELETE FROM sessions WHERE session_id = ?",
                (entity_id,),
            )
            self._connection.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to delete session: {e}")

    async def exists(self, entity_id: str) -> bool:
        """Check if a session exists.

        Args:
            entity_id: The unique identifier to check

        Returns:
            True if the session exists, False otherwise

        Raises:
            ConnectionError: If not connected to the database
        """
        if not self._connection:
            raise ConnectionError("Not connected to database")

        cursor = self._connection.execute(
            "SELECT 1 FROM sessions WHERE session_id = ?",
            (entity_id,),
        )
        return cursor.fetchone() is not None

    async def list_all(
        self,
        pagination: PaginationParams | None = None,
    ) -> PaginatedResult[Session]:
        """List all sessions with optional pagination.

        Args:
            pagination: Pagination parameters (offset, limit)

        Returns:
            Paginated result containing sessions and metadata

        Raises:
            ConnectionError: If not connected to the database
        """
        if not self._connection:
            raise ConnectionError("Not connected to database")

        pagination = pagination or PaginationParams()

        cursor = self._connection.execute("SELECT COUNT(*) as count FROM sessions")
        total = cursor.fetchone()["count"]

        cursor = self._connection.execute(
            """SELECT session_id, last_activity FROM sessions
               ORDER BY last_activity DESC LIMIT ? OFFSET ?""",
            (pagination.limit, pagination.offset),
        )

        sessions = []
        for row in cursor.fetchall():
            messages = await self._get_messages(row["session_id"])
            sessions.append(
                Session(
                    session_id=row["session_id"],
                    messages=messages,
                    last_activity=datetime.fromtimestamp(row["last_activity"]),
                )
            )

        return PaginatedResult(
            items=sessions,
            total=total,
            offset=pagination.offset,
            limit=pagination.limit,
        )

    async def find_by_filters(
        self,
        filters: list[Any],
        pagination: PaginationParams | None = None,
    ) -> PaginatedResult[Session]:
        """Find sessions matching the given filters.

        Args:
            filters: List of filter criteria
            pagination: Pagination parameters (offset, limit)

        Returns:
            Paginated result containing matching sessions

        Raises:
            ConnectionError: If not connected to the database
            RepositoryError: If filter operation fails
        """
        raise NotImplementedError("Filter-based search not implemented for sessions")

    async def count(self, filters: list[Any] | None = None) -> int:
        """Count sessions, optionally filtered.

        Args:
            filters: Optional list of filter criteria

        Returns:
            Number of matching sessions

        Raises:
            ConnectionError: If not connected to the database
        """
        if not self._connection:
            raise ConnectionError("Not connected to database")

        cursor = self._connection.execute("SELECT COUNT(*) as count FROM sessions")
        return cursor.fetchone()["count"]

    async def begin_transaction(self) -> Any:
        """Begin a database transaction.

        Returns:
            A transaction context

        Raises:
            ConnectionError: If not connected to the database
        """
        if not self._connection:
            raise ConnectionError("Not connected to database")

        self._connection.execute("BEGIN")
        return self._connection

    async def commit_transaction(self, transaction: Any) -> None:
        """Commit a database transaction.

        Args:
            transaction: The transaction handle from begin_transaction

        Raises:
            RepositoryError: If the transaction cannot be committed
        """
        try:
            transaction.commit()
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to commit transaction: {e}")

    async def rollback_transaction(self, transaction: Any) -> None:
        """Rollback a database transaction.

        Args:
            transaction: The transaction handle from begin_transaction

        Raises:
            RepositoryError: If the transaction cannot be rolled back
        """
        try:
            transaction.rollback()
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to rollback transaction: {e}")
