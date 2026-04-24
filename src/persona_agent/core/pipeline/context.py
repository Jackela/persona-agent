"""Pipeline context and result types."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChatContext:
    """Mutable context object passed between pipeline stages.

    Carries all state needed throughout the chat flow.
    Stages mutate this context in-place and return it via StageResult.
    """

    # Input parameters (set once at pipeline start)
    user_input: str
    session_id: str
    stream: bool = False
    enable_planning: bool = True
    on_plan_progress: Any = None

    # Mutable state (modified by stages)
    correlation_id: str | None = None
    messages: list[dict[str, str]] = field(default_factory=list)
    response: str | AsyncIterator[str] | None = None
    is_complete: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StageResult:
    """Result from a pipeline stage execution.

    should_continue=False signals pipeline short-circuit.
    This allows skill matching and planning to exit early.
    """

    context: ChatContext
    should_continue: bool = True
