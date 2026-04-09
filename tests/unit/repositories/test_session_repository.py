"""Unit tests for SessionRepository."""

import sqlite3
from datetime import datetime

import pytest

from persona_agent.repositories import Session
from persona_agent.repositories.base import (
    DuplicateEntityError,
    EntityNotFoundError,
    PaginationParams,
)
from persona_agent.repositories.session_repository import SessionRepository


class TestSessionRepository:
    """Test suite for SessionRepository."""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """Create a temporary database path."""
        return tmp_path / "test_chat.db"

    @pytest.fixture
    async def repo(self, temp_db_path):
        """Create a connected SessionRepository."""
        repository = SessionRepository(temp_db_path)
        await repository.connect()
        yield repository
        await repository.disconnect()

    @pytest.mark.asyncio
    async def test_connect_creates_database(self, temp_db_path):
        """Test that connect creates the database file."""
        # Arrange
        repo = SessionRepository(temp_db_path)

        # Act
        await repo.connect()

        # Assert
        assert temp_db_path.exists()
        await repo.disconnect()

    @pytest.mark.asyncio
    async def test_connect_creates_tables(self, temp_db_path):
        """Test that connect creates required tables."""
        # Arrange
        repo = SessionRepository(temp_db_path)
        await repo.connect()

        # Act - Verify tables exist by querying sqlite_master
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        # Assert
        assert "sessions" in tables
        assert "messages" in tables
        await repo.disconnect()

    @pytest.mark.asyncio
    async def test_is_connected_when_connected(self, repo):
        """Test is_connected returns True when connected."""
        # Act
        result = await repo.is_connected()

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_is_connected_when_not_connected(self, temp_db_path):
        """Test is_connected returns False when not connected."""
        # Arrange
        repo = SessionRepository(temp_db_path)

        # Act
        result = await repo.is_connected()

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_create_session(self, repo):
        """Test creating a new session."""
        # Arrange
        session = Session(
            session_id="test-session-123",
            messages=[{"role": "user", "content": "hello"}],
            last_activity=datetime.now(),
        )

        # Act
        result = await repo.create(session)

        # Assert
        assert result.session_id == "test-session-123"
        assert await repo.exists("test-session-123") is True

    @pytest.mark.asyncio
    async def test_create_duplicate_session_raises_error(self, repo):
        """Test creating duplicate session raises DuplicateEntityError."""
        # Arrange
        session = Session(session_id="test-session-123", messages=[], last_activity=datetime.now())
        await repo.create(session)

        # Act & Assert
        with pytest.raises(DuplicateEntityError):
            await repo.create(session)

    @pytest.mark.asyncio
    async def test_get_by_id_existing(self, repo):
        """Test getting an existing session by ID."""
        # Arrange
        session = Session(
            session_id="test-session-123",
            messages=[{"role": "user", "content": "hello"}],
            last_activity=datetime.now(),
        )
        await repo.create(session)

        # Act
        result = await repo.get_by_id("test-session-123")

        # Assert
        assert result is not None
        assert result.session_id == "test-session-123"

    @pytest.mark.asyncio
    async def test_get_by_id_nonexistent(self, repo):
        """Test getting non-existent session returns None."""
        # Act
        result = await repo.get_by_id("nonexistent")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_exists_true(self, repo):
        """Test exists returns True for existing session."""
        # Arrange
        session = Session(session_id="test-session-123", messages=[], last_activity=datetime.now())
        await repo.create(session)

        # Act
        result = await repo.exists("test-session-123")

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self, repo):
        """Test exists returns False for non-existent session."""
        # Act
        result = await repo.exists("nonexistent")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_existing(self, repo):
        """Test deleting an existing session."""
        # Arrange
        session = Session(session_id="test-session-123", messages=[], last_activity=datetime.now())
        await repo.create(session)

        # Act
        result = await repo.delete("test-session-123")

        # Assert
        assert result is True
        assert await repo.exists("test-session-123") is False

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, repo):
        """Test deleting non-existent session returns False."""
        # Act
        result = await repo.delete("nonexistent")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_list_all(self, repo):
        """Test listing all sessions."""
        # Arrange
        for i in range(3):
            session = Session(
                session_id=f"session-{i}",
                messages=[{"role": "user", "content": f"msg {i}"}],
                last_activity=datetime.now(),
            )
            await repo.create(session)

        # Act
        result = await repo.list_all()

        # Assert
        assert result.total == 3
        assert len(result.items) == 3

    @pytest.mark.asyncio
    async def test_list_all_with_pagination(self, repo):
        """Test listing sessions with pagination."""
        # Arrange
        for i in range(5):
            session = Session(session_id=f"session-{i}", messages=[], last_activity=datetime.now())
            await repo.create(session)

        # Act
        pagination = PaginationParams(offset=0, limit=2)
        result = await repo.list_all(pagination=pagination)

        # Assert
        assert result.total == 5
        assert len(result.items) == 2

    @pytest.mark.asyncio
    async def test_list_all_empty(self, repo):
        """Test listing sessions when none exist."""
        # Act
        result = await repo.list_all()

        # Assert
        assert result.total == 0
        assert len(result.items) == 0

    @pytest.mark.asyncio
    async def test_count(self, repo):
        """Test counting sessions."""
        # Arrange
        for i in range(3):
            session = Session(session_id=f"session-{i}", messages=[], last_activity=datetime.now())
            await repo.create(session)

        # Act
        result = await repo.count()

        # Assert
        assert result == 3

    @pytest.mark.asyncio
    async def test_update_existing(self, repo):
        """Test updating an existing session."""
        # Arrange
        session = Session(
            session_id="test-session-123",
            messages=[{"role": "user", "content": "old"}],
            last_activity=datetime.now(),
        )
        await repo.create(session)

        # Update
        session.messages = [{"role": "user", "content": "updated"}]

        # Act
        result = await repo.update(session)

        # Assert
        assert result.session_id == "test-session-123"
        retrieved = await repo.get_by_id("test-session-123")
        assert len(retrieved.messages) == 1

    @pytest.mark.asyncio
    async def test_update_nonexistent_raises_error(self, repo):
        """Test updating non-existent session raises EntityNotFoundError."""
        # Arrange
        session = Session(session_id="nonexistent", messages=[], last_activity=datetime.now())

        # Act & Assert
        with pytest.raises(EntityNotFoundError):
            await repo.update(session)

    @pytest.mark.asyncio
    async def test_context_manager(self, temp_db_path):
        """Test using repository as async context manager."""
        # Act
        async with SessionRepository(temp_db_path) as repo:
            # Assert - should be connected
            assert await repo.is_connected() is True

            # Create a session
            session = Session(session_id="test", messages=[], last_activity=datetime.now())
            await repo.create(session)

        # Repository disconnected after context exit

    @pytest.mark.asyncio
    async def test_disconnect_closes_connection(self, temp_db_path):
        """Test that disconnect properly closes the connection."""
        # Arrange
        repo = SessionRepository(temp_db_path)
        await repo.connect()

        # Act
        await repo.disconnect()

        # Assert - connection should be None after disconnect
        assert repo._connection is None

    @pytest.mark.asyncio
    async def test_get_session_with_multiple_messages(self, repo):
        """Test retrieving session preserves all messages."""
        # Arrange
        messages = [
            {"role": "user", "content": "msg1", "timestamp": 1234567890},
            {"role": "assistant", "content": "resp1", "timestamp": 1234567891},
            {"role": "user", "content": "msg2", "timestamp": 1234567892},
        ]
        session = Session(
            session_id="multi-msg-session", messages=messages, last_activity=datetime.now()
        )
        await repo.create(session)

        # Act
        result = await repo.get_by_id("multi-msg-session")

        # Assert
        assert len(result.messages) == 3
        assert result.messages[0]["role"] == "user"
        assert result.messages[0]["content"] == "msg1"
        assert result.messages[1]["role"] == "assistant"
        assert result.messages[1]["content"] == "resp1"

    @pytest.mark.asyncio
    async def test_find_by_filters_not_implemented(self, repo):
        """Test that find_by_filters raises NotImplementedError."""
        # Act & Assert
        with pytest.raises(NotImplementedError):
            await repo.find_by_filters([])

    @pytest.mark.asyncio
    async def test_transaction_methods(self, repo):
        """Test that transaction methods work correctly."""
        # Act & Assert - should not raise any exceptions
        transaction = await repo.begin_transaction()
        assert transaction is not None

        await repo.commit_transaction(transaction)

        # Test rollback on a new transaction
        transaction2 = await repo.begin_transaction()
        await repo.rollback_transaction(transaction2)

    @pytest.mark.asyncio
    async def test_database_path_creation(self, temp_db_path):
        """Test that database directory is created if it doesn't exist."""
        # Arrange
        nested_path = temp_db_path.parent / "nested" / "dir" / "test.db"

        # Act
        repo = SessionRepository(nested_path)
        await repo.connect()

        # Assert
        assert nested_path.parent.exists()
        await repo.disconnect()
