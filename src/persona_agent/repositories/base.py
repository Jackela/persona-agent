"""Base repository class and interfaces for the repository layer.

This module provides the abstract base class for all repositories in the
persona-agent system, implementing the Repository Pattern for data access.

The Repository Pattern abstracts data access logic, allowing the business
logic to remain agnostic of the underlying database implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from persona_agent.exceptions import PersonaAgentError

# Type variables for generic repository typing
T = TypeVar("T")
ID = TypeVar("ID")


@dataclass
class PaginationParams:
    """Parameters for paginated queries.

    Attributes:
        offset: Number of records to skip
        limit: Maximum number of records to return
    """

    offset: int = 0
    limit: int = 100


@dataclass
class PaginatedResult(Generic[T]):
    """Result of a paginated query.

    Attributes:
        items: List of entities returned
        total: Total number of matching records
        offset: Current offset
        limit: Current limit
    """

    items: list[T]
    total: int
    offset: int
    limit: int

    @property
    def has_more(self) -> bool:
        """Check if there are more results available."""
        return self.offset + len(self.items) < self.total


@dataclass
class QueryFilter:
    """Filter criteria for repository queries.

    Attributes:
        field: Field name to filter on
        operator: Comparison operator (eq, ne, gt, gte, lt, lte, like, in)
        value: Value to compare against
    """

    field: str
    operator: str
    value: Any


class RepositoryError(PersonaAgentError):
    """Base exception for repository errors."""

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message, code="REPOSITORY_ERROR", details=details)


class EntityNotFoundError(RepositoryError):
    """Raised when an entity is not found in the repository."""

    def __init__(self, entity_type: str, entity_id: object) -> None:
        """Initialize the error.

        Args:
            entity_type: Type of entity that was not found
            entity_id: ID of the entity that was not found
        """
        super().__init__(f"{entity_type} with id '{entity_id}' not found")
        self.entity_type = entity_type
        self.entity_id = entity_id


class DuplicateEntityError(RepositoryError):
    """Raised when attempting to create an entity that already exists."""

    def __init__(self, entity_type: str, entity_id: object) -> None:
        """Initialize the error.

        Args:
            entity_type: Type of entity that already exists
            entity_id: ID of the entity that already exists
        """
        super().__init__(f"{entity_type} with id '{entity_id}' already exists")
        self.entity_type = entity_type
        self.entity_id = entity_id


class ConnectionError(RepositoryError):
    """Raised when database connection fails."""

    pass


class BaseRepository(ABC, Generic[T, ID]):
    """Abstract base class for all repositories.

    This class defines the contract for data access operations, providing
    a clean separation between business logic and data persistence.

    Type Parameters:
        T: The entity type this repository manages
        ID: The type of the entity's identifier

    Example:
        class SessionRepository(BaseRepository[Session, str]):
            async def get_by_id(self, entity_id: str) -> Session | None:
                # Implementation
                pass

            # ... implement other abstract methods
    """

    def __init__(self) -> None:
        """Initialize the repository."""
        self._connected = False

    # ==================== Connection Management ====================

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the database.

        This method should initialize any connection pools, clients,
        or other resources needed for database access.

        Raises:
            ConnectionError: If the connection cannot be established
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the database.

        This method should release all resources and close connections.
        It is safe to call even if connect() was not called.
        """
        pass

    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if the repository is connected to the database.

        Returns:
            True if connected, False otherwise
        """
        pass

    async def __aenter__(self) -> BaseRepository[T, ID]:
        """Async context manager entry.

        Returns:
            The repository instance with active connection
        """
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
        """
        await self.disconnect()

    # ==================== CRUD Operations ====================

    @abstractmethod
    async def create(self, entity: T) -> T:
        """Create a new entity in the repository.

        Args:
            entity: The entity to create

        Returns:
            The created entity, potentially with updated fields (e.g., ID)

        Raises:
            DuplicateEntityError: If an entity with the same ID already exists
            ConnectionError: If not connected to the database
        """
        pass

    @abstractmethod
    async def get_by_id(self, entity_id: ID) -> T | None:
        """Retrieve an entity by its identifier.

        Args:
            entity_id: The unique identifier of the entity

        Returns:
            The entity if found, None otherwise

        Raises:
            ConnectionError: If not connected to the database
        """
        pass

    @abstractmethod
    async def update(self, entity: T) -> T:
        """Update an existing entity.

        Args:
            entity: The entity to update

        Returns:
            The updated entity

        Raises:
            EntityNotFoundError: If the entity does not exist
            ConnectionError: If not connected to the database
        """
        pass

    @abstractmethod
    async def delete(self, entity_id: ID) -> bool:
        """Delete an entity by its identifier.

        Args:
            entity_id: The unique identifier of the entity to delete

        Returns:
            True if the entity was deleted, False if it didn't exist

        Raises:
            ConnectionError: If not connected to the database
        """
        pass

    @abstractmethod
    async def exists(self, entity_id: ID) -> bool:
        """Check if an entity exists.

        Args:
            entity_id: The unique identifier to check

        Returns:
            True if the entity exists, False otherwise

        Raises:
            ConnectionError: If not connected to the database
        """
        pass

    # ==================== Query Operations ====================

    @abstractmethod
    async def list_all(
        self,
        pagination: PaginationParams | None = None,
    ) -> PaginatedResult[T]:
        """List all entities with optional pagination.

        Args:
            pagination: Pagination parameters (offset, limit)

        Returns:
            Paginated result containing entities and metadata

        Raises:
            ConnectionError: If not connected to the database
        """
        pass

    @abstractmethod
    async def find_by_filters(
        self,
        filters: list[QueryFilter],
        pagination: PaginationParams | None = None,
    ) -> PaginatedResult[T]:
        """Find entities matching the given filters.

        Args:
            filters: List of filter criteria
            pagination: Pagination parameters (offset, limit)

        Returns:
            Paginated result containing matching entities

        Raises:
            ConnectionError: If not connected to the database
        """
        pass

    @abstractmethod
    async def count(self, filters: list[QueryFilter] | None = None) -> int:
        """Count entities, optionally filtered.

        Args:
            filters: Optional list of filter criteria

        Returns:
            Number of matching entities

        Raises:
            ConnectionError: If not connected to the database
        """
        pass

    # ==================== Transaction Support ====================

    @abstractmethod
    async def begin_transaction(self) -> Any:
        """Begin a database transaction.

        Returns:
            A transaction context or handle

        Raises:
            ConnectionError: If not connected to the database
        """
        pass

    @abstractmethod
    async def commit_transaction(self, transaction: Any) -> None:
        """Commit a database transaction.

        Args:
            transaction: The transaction handle from begin_transaction

        Raises:
            RepositoryError: If the transaction cannot be committed
        """
        pass

    @abstractmethod
    async def rollback_transaction(self, transaction: Any) -> None:
        """Rollback a database transaction.

        Args:
            transaction: The transaction handle from begin_transaction

        Raises:
            RepositoryError: If the transaction cannot be rolled back
        """
        pass


class BaseUnitOfWork(ABC):
    """Abstract base class for Unit of Work pattern.

    The Unit of Work pattern maintains a list of objects affected by a
    business transaction and coordinates the writing out of changes.

    This is typically used alongside repositories to ensure atomicity
    across multiple operations.

    Example:
        async with unit_of_work:
            session_repo.create(session)
            user_repo.update(user)
            await unit_of_work.commit()
    """

    @abstractmethod
    async def __aenter__(self) -> BaseUnitOfWork:
        """Enter the unit of work context."""
        pass

    @abstractmethod
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the unit of work context, rolling back if not committed."""
        pass

    @abstractmethod
    async def commit(self) -> None:
        """Commit all pending changes.

        Raises:
            RepositoryError: If the commit fails
        """
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback all pending changes.

        Raises:
            RepositoryError: If the rollback fails
        """
        pass
