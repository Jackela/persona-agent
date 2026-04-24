"""Memory storage stage for chat pipeline."""

from persona_agent.core.memory_store import MemoryStore as MemoryStoreClass
from persona_agent.core.pipeline.context import ChatContext, StageResult


class MemoryStorageStage:
    """Stores the conversation exchange in memory.

    Only stores for non-streaming responses. Streaming responses
    handle storage internally via the async iterator wrapper.
    """

    def __init__(self, memory_store: MemoryStoreClass):
        self.memory_store = memory_store

    async def process(self, context: ChatContext) -> StageResult:
        if context.stream:
            return StageResult(context, should_continue=True)

        if context.response and isinstance(context.response, str):
            await self.memory_store.store(
                session_id=context.session_id,
                user_message=context.user_input,
                assistant_message=context.response,
            )

        return StageResult(context, should_continue=True)
