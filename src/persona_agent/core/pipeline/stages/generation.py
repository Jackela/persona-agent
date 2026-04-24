"""Response generation stage for chat pipeline."""

from collections.abc import AsyncIterator

from persona_agent.core.memory_store import MemoryStore
from persona_agent.core.persona_manager import PersonaManager
from persona_agent.core.pipeline.context import ChatContext, StageResult
from persona_agent.utils.llm_client import LLMClient


class ResponseGenerationStage:
    """Generates response using LLM and applies linguistic style.

    Handles both streaming and non-streaming modes.
    For streaming, returns an async iterator wrapper that stores
    memory after the stream is fully consumed.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        persona_manager: PersonaManager,
        memory_store: MemoryStore,
    ):
        self.llm_client = llm_client
        self.persona_manager = persona_manager
        self.memory_store = memory_store

    async def process(self, context: ChatContext) -> StageResult:
        if context.stream:
            context.response = self._create_streaming_response(context)
            context.is_complete = True
            return StageResult(context, should_continue=False)

        response = await self.llm_client.chat(context.messages)
        styled = self._apply_style(response.content)
        context.response = styled
        return StageResult(context, should_continue=True)

    def _apply_style(self, text: str) -> str:
        return self.persona_manager.apply_linguistic_style(
            text,
            use_kaomoji=True,
            use_nickname=True,
        )

    def _create_streaming_response(self, context: ChatContext) -> AsyncIterator[str]:
        """Create async iterator that stores memory after streaming completes."""

        async def _stream() -> AsyncIterator[str]:
            full_response = []
            async for chunk in self.llm_client.chat_stream(context.messages):
                full_response.append(chunk)
                yield chunk

            complete = "".join(full_response)
            styled = self._apply_style(complete)

            await self.memory_store.store(
                session_id=context.session_id,
                user_message=context.user_input,
                assistant_message=styled,
            )
            context.response = styled

        return _stream()
