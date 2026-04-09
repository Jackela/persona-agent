"""Session service for managing chat sessions.

This module provides the SessionService class for managing chat sessions
through the SessionRepository, providing a clean API for session operations.
"""

from pathlib import Path
from typing import Any

from persona_agent.repositories import Session, SessionRepository
from persona_agent.utils.exceptions import PersonaAgentError


class SessionServiceError(PersonaAgentError):
    """Base exception for session service errors."""

    def __init__(self, message: str, session_id: str | None = None, **kwargs):
        super().__init__(message, **kwargs)
        if session_id:
            self.details["session_id"] = session_id


class SessionNotFoundError(SessionServiceError):
    """Raised when a session is not found."""

    def __init__(self, session_id: str, **kwargs):
        super().__init__(
            f"Session '{session_id}' not found",
            session_id=session_id,
            code="SESSION_NOT_FOUND",
            **kwargs,
        )


class SessionDeleteError(SessionServiceError):
    """Raised when session deletion fails."""

    def __init__(self, session_id: str, reason: str, **kwargs):
        super().__init__(
            f"Failed to delete session '{session_id}': {reason}",
            session_id=session_id,
            code="SESSION_DELETE_ERROR",
            **kwargs,
        )
        self.details["reason"] = reason


class SessionService:
    """Service for managing chat sessions.

    This service wraps the SessionRepository to provide a clean API for
    session management operations. It handles database connections and
    provides methods for listing, getting, creating, and deleting sessions.

    Attributes:
        _repo: SessionRepository instance for data access

    Example:
        >>> service = SessionService()
        >>> sessions = await service.list_sessions()
        >>> session = await service.get_session("abc123")
    """

    def __init__(
        self,
        db_path: str | Path = "memory/persona_agent.db",
        session_repo: SessionRepository | None = None,
    ) -> None:
        """Initialize the session service.

        Args:
            db_path: Path to the SQLite database file.
                Only used if session_repo is not provided.
            session_repo: Optional SessionRepository instance.
                If provided, this repository will be used instead of creating a new one.
        """
        self._repo = session_repo or SessionRepository(db_path)

    async def _ensure_connected(self) -> None:
        """Ensure repository is connected to database."""
        if not await self._repo.is_connected():
            await self._repo.connect()

    async def list_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        """List recent chat sessions.

        Returns a list of sessions with their message count and last activity time.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of session dictionaries with keys: session_id, message_count, last_activity

        Example:
            >>> service = SessionService()
            >>> sessions = await service.list_sessions(limit=10)
            >>> print(sessions[0]["session_id"])
        """
        await self._ensure_connected()
        result = await self._repo.list_all()
        sessions = []
        for session in result.items[:limit]:
            sessions.append(
                {
                    "session_id": session.session_id,
                    "message_count": len(session.messages),
                    "last_activity": session.last_activity,
                }
            )
        return sessions

    async def get_session(self, session_id: str) -> Session:
        """Get a session by its ID.

        Args:
            session_id: The unique identifier of the session

        Returns:
            The Session object

        Raises:
            SessionNotFoundError: If the session doesn't exist
        """
        await self._ensure_connected()
        session = await self._repo.get_by_id(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    async def get_session_info(self, session_id: str) -> dict[str, Any]:
        """Get detailed information about a session.

        Args:
            session_id: The unique identifier of the session

        Returns:
            Dictionary containing session information including:
            - session_id
            - message_count
            - first_activity
            - last_activity
            - recent_messages

        Raises:
            SessionNotFoundError: If the session doesn't exist
        """
        session = await self.get_session(session_id)
        messages = session.messages
        return {
            "session_id": session.session_id,
            "message_count": len(messages),
            "first_activity": messages[0]["timestamp"] if messages else session.last_activity,
            "last_activity": session.last_activity,
            "recent_messages": messages[-5:] if len(messages) > 5 else messages,
        }

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages.

        Args:
            session_id: The unique identifier of the session to delete

        Returns:
            True if the session was deleted, False if it didn't exist

        Raises:
            SessionDeleteError: If deletion fails
        """
        await self._ensure_connected()
        try:
            result = await self._repo.delete(session_id)
            if not result:
                raise SessionNotFoundError(session_id)
            return True
        except Exception as e:
            raise SessionDeleteError(session_id, str(e)) from e

    async def session_exists(self, session_id: str) -> bool:
        """Check if a session exists.

        Args:
            session_id: The session ID to check

        Returns:
            True if the session exists, False otherwise
        """
        await self._ensure_connected()
        return await self._repo.exists(session_id)

    async def close(self) -> None:
        """Close the database connection."""
        await self._repo.disconnect()

    async def __aenter__(self) -> "SessionService":
        """Async context manager entry."""
        await self._ensure_connected()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
