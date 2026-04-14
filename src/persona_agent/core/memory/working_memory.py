"""Working memory - recent conversation context."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class Message:
    """A simple message structure."""

    role: str
    content: str


class WorkingMemory:
    """Working memory - recent conversation context (3-5 exchanges).

    Working memory always stays in context and provides immediate
    access to the most recent conversation turns.

    Each exchange contains both user message and assistant response.
    """

    def __init__(self, max_size: int = 5):
        """Initialize working memory.

        Args:
            max_size: Maximum number of exchanges to keep (default: 5)
        """
        self.max_size = max_size
        self._exchanges: deque[dict[str, str]] = deque(maxlen=max_size)

    def add_exchange(self, user_msg: str, assistant_msg: str) -> None:
        """Add a conversation exchange to working memory.

        Args:
            user_msg: User's message
            assistant_msg: Assistant's response
        """
        self._exchanges.append(
            {
                "user": user_msg,
                "assistant": assistant_msg,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    def get_recent(self, n: int | None = None) -> list[Message]:
        """Get recent messages from working memory.

        Args:
            n: Number of exchanges to retrieve. If None, returns all.

        Returns:
            List of Message objects (flattened user/assistant pairs)
        """
        if n is None or n > len(self._exchanges):
            n = len(self._exchanges)

        exchanges = list(self._exchanges)[-n:]
        messages: list[Message] = []

        for exchange in exchanges:
            messages.append(Message(role="user", content=exchange["user"]))
            messages.append(Message(role="assistant", content=exchange["assistant"]))

        return messages

    def to_prompt_context(self) -> str:
        """Format working memory for inclusion in prompt.

        Returns:
            Formatted string with recent conversation context
        """
        if not self._exchanges:
            return ""

        lines = ["## Recent Conversation"]
        for i, exchange in enumerate(self._exchanges, 1):
            lines.append(f"\n### Exchange {i}")
            lines.append(f"User: {exchange['user']}")
            lines.append(f"Assistant: {exchange['assistant']}")

        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all exchanges from working memory."""
        self._exchanges.clear()

    def __len__(self) -> int:
        """Return the number of exchanges in working memory."""
        return len(self._exchanges)


__all__ = ["Message", "WorkingMemory"]
