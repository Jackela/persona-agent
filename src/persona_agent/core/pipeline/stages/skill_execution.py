"""Skill execution stage for chat pipeline."""

from persona_agent.core.memory_store import MemoryStore
from persona_agent.core.persona_manager import PersonaManager
from persona_agent.core.pipeline.context import ChatContext, StageResult
from persona_agent.skills.base import SkillContext
from persona_agent.skills.registry import SkillRegistry


class SkillExecutionStage:
    """Attempts to handle input via registered skills.

    Skills are checked in priority order. If a skill matches and succeeds,
    the response is stored and the pipeline short-circuits.
    """

    def __init__(
        self,
        skill_registry: SkillRegistry,
        persona_manager: PersonaManager,
        memory_store: MemoryStore,
    ):
        self.skill_registry = skill_registry
        self.persona_manager = persona_manager
        self.memory_store = memory_store

    async def process(self, context: ChatContext) -> StageResult:
        mood_engine = self.persona_manager.get_mood_engine()
        skill_context = SkillContext(
            user_input=context.user_input,
            conversation_history=[],
            current_mood=mood_engine.current_state.name if mood_engine else "neutral",
            session_id=context.session_id,
            memory_store=self.memory_store,
            persona_manager=self.persona_manager,
        )

        result = await self.skill_registry.execute_matching(skill_context)

        if result and result.success and result.response:
            # Store the skill-handled exchange
            await self.memory_store.store(
                session_id=context.session_id,
                user_message=context.user_input,
                assistant_message=result.response,
            )
            context.response = result.response
            context.is_complete = True
            return StageResult(context, should_continue=False)

        return StageResult(context, should_continue=True)
