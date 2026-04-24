"""Pipeline orchestrator for chat flow."""

import logging

from persona_agent.core.pipeline.context import ChatContext
from persona_agent.core.pipeline.stage import PipelineStage

logger = logging.getLogger(__name__)


class ChatPipeline:
    """Orchestrates execution of chat pipeline stages.

    Executes stages sequentially. Supports short-circuiting when a stage
    sets should_continue=False. Guarantees cleanup stage runs in finally block.

    The pipeline itself is configurable - stages can be reordered,
    replaced, or removed via constructor injection.
    """

    def __init__(
        self,
        stages: list[PipelineStage],
        cleanup_stage: PipelineStage | None = None,
    ):
        """Initialize pipeline with stages.

        Args:
            stages: Ordered list of pipeline stages to execute
            cleanup_stage: Optional stage that always runs in finally block
        """
        self.stages = stages
        self.cleanup_stage = cleanup_stage

    async def execute(self, context: ChatContext) -> ChatContext:
        """Execute all stages sequentially.

        Args:
            context: Initial chat context

        Returns:
            Final context after all stages complete
        """
        try:
            for stage in self.stages:
                logger.debug(f"Executing stage: {stage.__class__.__name__}")
                result = await stage.process(context)
                context = result.context

                if not result.should_continue:
                    logger.debug(f"Pipeline short-circuited by {stage.__class__.__name__}")
                    break

        except Exception:
            logger.exception("Pipeline execution failed")
            raise
        finally:
            if self.cleanup_stage:
                try:
                    await self.cleanup_stage.process(context)
                except Exception:
                    logger.exception("Cleanup stage failed")
                    # Don't let cleanup errors mask original error

        return context
