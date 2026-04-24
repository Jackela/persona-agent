"""Validation stage for chat pipeline."""

import uuid

from persona_agent.core.pipeline.context import ChatContext, StageResult
from persona_agent.utils.llm_client import LLMClient
from persona_agent.utils.logging_config import set_correlation_id


class ValidationStage:
    """Validates that the engine is ready to process a chat request."""

    def __init__(self, llm_client: LLMClient | None) -> None:
        self.llm_client = llm_client

    async def process(self, context: ChatContext) -> StageResult:
        if not self.llm_client:
            raise RuntimeError("LLM client not configured")

        context.correlation_id = str(uuid.uuid4())
        set_correlation_id(context.correlation_id)

        return StageResult(context, should_continue=True)
