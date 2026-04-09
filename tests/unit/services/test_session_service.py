"""Unit tests for SessionService."""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock

from persona_agent.services.session_service import (
    SessionService,
    SessionNotFoundError,
    SessionDeleteError,
)
from persona_agent.repositories import Session


class TestSessionService:
    """Test suite for SessionService."""

    @pytest.fixture
    def service(self):
        """Create a SessionService instance."""
        return SessionService()

    @pytest.fixture
    def mock_repo(self):
        """Create a mock SessionRepository."""
        mock = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_list_sessions(self, service, mock_repo):
        """Test listing sessions."""
        # Arrange
        mock_session = Session(
            session_id="test-123",
            messages=[{"user": "hello"}, {"assistant": "hi"}],
            last_activity=datetime.now(),
        )
        mock_repo.list_all.return_value = Mock(items=[mock_session], total=1)
        service._repo = mock_repo

        # Act
        result = await service.list_sessions(limit=10)

        # Assert
        assert len(result) == 1
        assert result[0]["session_id"] == "test-123"
        assert result[0]["message_count"] == 2

    @pytest.mark.asyncio
    async def test_list_sessions_empty(self, service, mock_repo):
        """Test listing sessions when none exist."""
        # Arrange
        mock_repo.list_all.return_value = Mock(items=[], total=0)
        service._repo = mock_repo

        # Act
        result = await service.list_sessions()

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_get_session_success(self, service, mock_repo):
        """Test getting an existing session."""
        # Arrange
        mock_session = Session(session_id="test-123", messages=[], last_activity=datetime.now())
        mock_repo.get_by_id.return_value = mock_session
        service._repo = mock_repo

        # Act
        result = await service.get_session("test-123")

        # Assert
        assert result == mock_session
        mock_repo.get_by_id.assert_called_once_with("test-123")

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, service, mock_repo):
        """Test getting non-existent session raises error."""
        # Arrange
        mock_repo.get_by_id.return_value = None
        service._repo = mock_repo

        # Act & Assert
        with pytest.raises(SessionNotFoundError) as exc_info:
            await service.get_session("nonexistent")

        assert "nonexistent" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_session_info(self, service, mock_repo):
        """Test getting detailed session info."""
        # Arrange
        mock_session = Session(
            session_id="test-123",
            messages=[
                {"user_message": "hello", "timestamp": datetime(2024, 1, 1, 10, 0)},
                {"user_message": "world", "timestamp": datetime(2024, 1, 1, 10, 5)},
            ],
            last_activity=datetime(2024, 1, 1, 10, 5),
        )
        mock_repo.get_by_id.return_value = mock_session
        service._repo = mock_repo

        # Act
        result = await service.get_session_info("test-123")

        # Assert
        assert result["session_id"] == "test-123"
        assert result["message_count"] == 2
        assert len(result["recent_messages"]) == 2

    @pytest.mark.asyncio
    async def test_delete_session_success(self, service, mock_repo):
        """Test deleting an existing session."""
        # Arrange
        mock_repo.delete.return_value = True
        service._repo = mock_repo

        # Act
        result = await service.delete_session("test-123")

        # Assert
        assert result is True
        mock_repo.delete.assert_called_once_with("test-123")

    @pytest.mark.asyncio
    async def test_delete_session_not_found(self, service, mock_repo):
        """Test deleting non-existent session raises error."""
        # Arrange
        mock_repo.delete.return_value = False
        service._repo = mock_repo

        # Act & Assert
        with pytest.raises(SessionDeleteError) as exc_info:
            await service.delete_session("nonexistent")

        assert "nonexistent" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_session_exists_true(self, service, mock_repo):
        """Test checking if session exists (True case)."""
        # Arrange
        mock_repo.exists.return_value = True
        service._repo = mock_repo

        # Act
        result = await service.session_exists("test-123")

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_session_exists_false(self, service, mock_repo):
        """Test checking if session exists (False case)."""
        # Arrange
        mock_repo.exists.return_value = False
        service._repo = mock_repo

        # Act
        result = await service.session_exists("test-123")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_ensure_connected_when_not_connected(self, service, mock_repo):
        """Test ensuring connection when not connected."""
        # Arrange
        mock_repo.is_connected.return_value = False
        service._repo = mock_repo

        # Act
        await service._ensure_connected()

        # Assert
        mock_repo.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_connected_when_already_connected(self, service, mock_repo):
        """Test ensuring connection when already connected."""
        # Arrange
        mock_repo.is_connected.return_value = True
        service._repo = mock_repo

        # Act
        await service._ensure_connected()

        # Assert
        mock_repo.connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_close(self, service, mock_repo):
        """Test closing the service."""
        # Arrange
        service._repo = mock_repo

        # Act
        await service.close()

        # Assert
        mock_repo.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_context_manager(self, service, mock_repo):
        """Test using service as async context manager."""
        # Arrange
        mock_repo.is_connected.return_value = False
        service._repo = mock_repo

        # Act
        async with service as svc:
            assert svc == service

        # Assert
        mock_repo.connect.assert_called_once()
        mock_repo.disconnect.assert_called_once()

    def test_session_service_error_details(self):
        """Test that SessionServiceError includes proper details."""
        # Arrange & Act
        error = SessionNotFoundError("test-session")

        # Assert
        assert error.details["session_id"] == "test-session"
        assert error.code == "SESSION_NOT_FOUND"
        assert "test-session" in str(error)

    def test_session_delete_error_with_reason(self):
        """Test SessionDeleteError includes reason in details."""
        # Arrange & Act
        error = SessionDeleteError("test-session", "Database locked")

        # Assert
        assert error.details["reason"] == "Database locked"
        assert error.code == "SESSION_DELETE_ERROR"
