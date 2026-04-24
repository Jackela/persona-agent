"""Context preparation stage for chat pipeline."""

from persona_agent.core.memory_store import MemoryStore
from persona_agent.core.persona_manager import PersonaManager
from persona_agent.core.pipeline.context import ChatContext, StageResult


class ContextPreparationStage:
    """Prepares the conversation context for LLM generation.

    Updates mood, builds system prompt, retrieves memories,
    and assembles the message list for the LLM.
    """

    def __init__(
        self,
        persona_manager: PersonaManager,
        memory_store: MemoryStore,
        memory_limit: int = 10,
    ):
        self.persona_manager = persona_manager
        self.memory_store = memory_store
        self.memory_limit = memory_limit

    async def process(self, context: ChatContext) -> StageResult:
        self.persona_manager.update_mood(context.user_input)

        system_prompt = self.persona_manager.build_system_prompt()
        context.messages = [{"role": "system", "content": system_prompt}]

        memories = await self.memory_store.retrieve_recent(
            context.session_id, limit=self.memory_limit
        )
        for memory in memories:
            context.messages.append({"role": "user", "content": memory.user_message})
            context.messages.append({"role": "assistant", "content": memory.assistant_message})

        context.messages.append({"role": "user", "content": context.user_input})

        return StageResult(context, should_continue=True)
