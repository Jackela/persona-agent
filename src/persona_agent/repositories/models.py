"""Repository models for persona-agent.

This module contains dataclasses representing entities stored in repositories.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Session:
    """Represents a chat session.

    A session contains a unique identifier, a list of messages exchanged
    during the session, and a timestamp of the last activity.

    Attributes:
        session_id: Unique identifier for the session
        messages: List of messages in the session
        last_activity: Timestamp of the last activity in the session
    """

    session_id: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    last_activity: datetime = field(default_factory=datetime.now)
