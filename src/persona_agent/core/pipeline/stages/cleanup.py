"""Cleanup stage for chat pipeline."""

from persona_agent.core.pipeline.context import ChatContext, StageResult
from persona_agent.utils.logging_config import clear_correlation_id


class CleanupStage:
    """Cleans up resources after pipeline execution.

    This stage runs in the finally block of the pipeline,
    ensuring cleanup happens even if earlier stages fail.
    """

    async def process(self, context: ChatContext) -> StageResult:
        clear_correlation_id()
        return StageResult(context, should_continue=True)
