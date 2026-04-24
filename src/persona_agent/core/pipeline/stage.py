"""Pipeline stage protocol."""

from typing import Protocol

from persona_agent.core.pipeline.context import ChatContext, StageResult


class PipelineStage(Protocol):
    """Protocol for chat pipeline stages.

    Each stage implements a single responsibility in the chat flow.
    Stages are composable, testable, and configurable.
    """

    async def process(self, context: ChatContext) -> StageResult:
        """Execute this stage's logic.

        Args:
            context: Current pipeline context with all accumulated state

        Returns:
            StageResult containing updated context and continuation flag.
            Set should_continue=False to short-circuit the pipeline.
        """
        ...
