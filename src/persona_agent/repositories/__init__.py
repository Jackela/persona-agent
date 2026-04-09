"""Repository layer for persona-agent.

This module provides the repository pattern implementation for data access,
including the base repository class, pagination support, and custom exceptions.
"""

from persona_agent.repositories.base import (
    BaseRepository,
    BaseUnitOfWork,
    ConnectionError,
    DuplicateEntityError,
    EntityNotFoundError,
    PaginatedResult,
    PaginationParams,
    QueryFilter,
    RepositoryError,
)
from persona_agent.repositories.models import Session
from persona_agent.repositories.session_repository import SessionRepository

__all__ = [
    "BaseRepository",
    "BaseUnitOfWork",
    "ConnectionError",
    "DuplicateEntityError",
    "EntityNotFoundError",
    "PaginatedResult",
    "PaginationParams",
    "QueryFilter",
    "RepositoryError",
    "Session",
    "SessionRepository",
]
