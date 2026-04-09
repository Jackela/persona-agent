"""Test mocks and stubs.

Mock implementations for external dependencies.
"""

from typing import Any, Optional
from unittest.mock import MagicMock


class MockLLMClient:
    """Mock LLM client for testing."""

    def __init__(self, responses: Optional[list[str]] = None):
        """Initialize mock client.

        Args:
            responses: Predefined responses to return
        """
        self.responses = responses or ["This is a mock response."]
        self.call_count = 0
        self.last_prompt: Optional[str] = None
        self.history: list[dict[str, Any]] = []

    async def chat(self, prompt: str, **kwargs: Any) -> str:
        """Mock chat method.

        Args:
            prompt: The prompt sent to LLM
            **kwargs: Additional parameters

        Returns:
            Mock response string
        """
        self.last_prompt = prompt
        self.call_count += 1
        self.history.append({"prompt": prompt, "kwargs": kwargs})

        if self.call_count <= len(self.responses):
            return self.responses[self.call_count - 1]
        return self.responses[-1] if self.responses else "Mock response"

    def reset(self) -> None:
        """Reset mock state."""
        self.call_count = 0
        self.last_prompt = None
        self.history.clear()


class MockMemoryStore:
    """Mock memory store for testing."""

    def __init__(self):
        """Initialize mock memory store."""
        self.memories: dict[str, list[dict[str, Any]]] = {}
        self.search_results: list[dict[str, Any]] = []

    async def add(self, user_id: str, content: str, **metadata: Any) -> str:
        """Mock add memory.

        Args:
            user_id: User identifier
            content: Memory content
            **metadata: Additional metadata

        Returns:
            Memory ID
        """
        import uuid

        memory_id = str(uuid.uuid4())
        if user_id not in self.memories:
            self.memories[user_id] = []
        memory = {
            "id": memory_id,
            "content": content,
            "metadata": metadata,
            "created_at": "2024-01-01T00:00:00",
        }
        self.memories[user_id].append(memory)
        return memory_id

    async def search(self, user_id: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Mock search memories."""
        return self.search_results

    async def get(self, user_id: str, memory_id: str) -> Optional[dict[str, Any]]:
        """Mock get memory by ID."""
        for memory in self.memories.get(user_id, []):
            if memory["id"] == memory_id:
                return memory
        return None

    def set_search_results(self, results: list[dict[str, Any]]) -> None:
        """Set predefined search results."""
        self.search_results = results


class MockSkill:
    """Mock skill for testing."""

    def __init__(self, name: str = "mock_skill", enabled: bool = True):
        """Initialize mock skill.

        Args:
            name: Skill name
            enabled: Whether skill is enabled
        """
        self.name = name
        self.enabled = enabled
        self.call_count = 0
        self.last_args: Optional[dict[str, Any]] = None
        self.return_value: Any = {"status": "success", "result": "Mock skill result"}

    async def execute(self, **kwargs: Any) -> Any:
        """Mock execute method.

        Args:
            **kwargs: Execution arguments

        Returns:
            Mock result
        """
        self.call_count += 1
        self.last_args = kwargs
        return self.return_value

    def set_return_value(self, value: Any) -> None:
        """Set the return value for execute.

        Args:
            value: Value to return
        """
        self.return_value = value


class MockChromaDB:
    """Mock ChromaDB client for testing."""

    def __init__(self):
        """Initialize mock ChromaDB."""
        self.collections: dict[str, Any] = {}
        self.embeddings: list[list[float]] = []

    def get_or_create_collection(self, name: str, **kwargs: Any) -> MagicMock:
        """Mock get or create collection.

        Args:
            name: Collection name
            **kwargs: Additional arguments

        Returns:
            Mock collection
        """
        if name not in self.collections:
            self.collections[name] = MagicMock()
        return self.collections[name]

    def reset(self) -> None:
        """Reset mock state."""
        self.collections.clear()
        self.embeddings.clear()
