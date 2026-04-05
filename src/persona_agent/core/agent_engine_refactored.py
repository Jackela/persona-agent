"""Main agent engine for persona-agent (refactored with new architecture).

This module provides a refactored AgentEngine that integrates the new
architecture components:
- LayeredPromptEngine for three-layer prompt building with RoleRAG
- CognitiveEmotionalEngine for dual-path processing
- HierarchicalMemory for three-layer memory system
- ConsistencyValidator for response validation
- AdaptiveUserModeling for user preference learning
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from persona_agent.core.cognitive_emotional_engine import (
    CognitiveEmotionalEngine,
    create_neutral_emotional_state,
)
from persona_agent.core.consistency_validator import ConsistencyValidator, ValidationConfig
from persona_agent.core.hierarchical_memory import HierarchicalMemory
from persona_agent.core.memory_store import MemoryStore
from persona_agent.core.persona_manager import PersonaManager
from persona_agent.core.prompt_engine import LayeredPromptEngine, create_layered_prompt_engine
from persona_agent.core.schemas import (
    CoreIdentity,
    DynamicContext,
    EmotionalState,
    KnowledgeBoundary,
    TaskContext,
)
from persona_agent.core.user_modeling import AdaptiveUserModeling, InMemoryUserModelStorage
from persona_agent.mcp.client import MCPClient, get_mcp_client
from persona_agent.skills.base import SkillContext
from persona_agent.skills.registry import SkillRegistry, get_registry
from persona_agent.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


class NewArchitectureAgentEngine:
    """Refactored agent engine using the new architecture components.

    This engine integrates:
    1. LayeredPromptEngine - Three-layer prompts with RoleRAG
    2. CognitiveEmotionalEngine - Dual-path cognitive-emotional processing
    3. HierarchicalMemory - Three-layer memory (working/episodic/semantic)
    4. ConsistencyValidator - Multi-layer response validation
    5. AdaptiveUserModeling - Real-time user preference learning

    The engine maintains backward compatibility with the old interface while
    providing enhanced capabilities through the new architecture.
    """

    def __init__(
        self,
        persona_manager: PersonaManager | None = None,
        memory_store: MemoryStore | None = None,
        llm_client: LLMClient | None = None,
        session_id: str | None = None,
        skill_registry: SkillRegistry | None = None,
        mcp_client: MCPClient | None = None,
        # New architecture components
        use_new_architecture: bool = True,
        enable_validation: bool = True,
        enable_user_modeling: bool = True,
        emotional_decay_rate: float = 0.1,
    ):
        """Initialize the refactored agent engine.

        Args:
            persona_manager: Legacy persona manager (used for character config)
            memory_store: Legacy memory store (migrated to hierarchical memory)
            llm_client: LLM client for generation
            session_id: Session identifier
            skill_registry: Skill registry for executing skills
            mcp_client: MCP client for tool execution
            use_new_architecture: Whether to use new architecture components
            enable_validation: Whether to enable response validation
            enable_user_modeling: Whether to enable user modeling
            emotional_decay_rate: Rate of emotional state decay over time
        """
        self.session_id = session_id or str(uuid.uuid4())
        self.llm_client = llm_client
        self.skill_registry = skill_registry or get_registry()

        # Legacy components (for backward compatibility)
        self.persona_manager = persona_manager or PersonaManager()
        self.memory_store = memory_store or MemoryStore()
        self.mcp_client = mcp_client or get_mcp_client(memory_store=self.memory_store)

        # New architecture flag
        self.use_new_architecture = use_new_architecture

        if not use_new_architecture:
            logger.info("AgentEngine initialized in legacy mode")
            return

        # Initialize new architecture components
        self._init_new_architecture(
            enable_validation=enable_validation,
            enable_user_modeling=enable_user_modeling,
            emotional_decay_rate=emotional_decay_rate,
        )

        logger.info(f"NewArchitectureAgentEngine initialized (session: {self.session_id})")

    def _init_new_architecture(
        self,
        enable_validation: bool,
        enable_user_modeling: bool,
        emotional_decay_rate: float,
    ) -> None:
        """Initialize new architecture components."""
        # Get character configuration from persona manager
        char = self.persona_manager.get_character()
        if char:
            # Build CoreIdentity from character
            self.core_identity = CoreIdentity(
                name=char.name,
                version="1.0.0",
                backstory=char.backstory or "",
                values={
                    "values": char.core_values if hasattr(char, "core_values") else [],
                    "fears": [],
                    "desires": [],
                    "boundaries": [],
                },
                behavioral_matrix={
                    "must_always": [],
                    "must_never": char.forbidden_topics
                    if hasattr(char, "forbidden_topics")
                    else [],
                    "should_avoid": [],
                },
            )

            # Build KnowledgeBoundary
            self.knowledge_boundary = KnowledgeBoundary(
                known_domains=char.knowledge_domains if hasattr(char, "knowledge_domains") else [],
                known_entities=[],
                unknown_domains=[],
                confidence=0.8,
            )
        else:
            # Default identity
            self.core_identity = CoreIdentity(
                name="Assistant",
                backstory="A helpful AI assistant.",
            )
            self.knowledge_boundary = KnowledgeBoundary()

        # Initialize LayeredPromptEngine
        self.prompt_engine = create_layered_prompt_engine(
            {
                "name": self.core_identity.name,
                "backstory": self.core_identity.backstory,
                "core_values": self.core_identity.values.dict()
                if self.core_identity.values
                else {},
                "knowledge_domains": self.knowledge_boundary.known_domains,
            },
            llm_client=self.llm_client,
        )

        # Initialize HierarchicalMemory
        self.hierarchical_memory = HierarchicalMemory()

        # Initialize CognitiveEmotionalEngine
        self.cognitive_emotional_engine = CognitiveEmotionalEngine(
            llm_client=self.llm_client,
            initial_emotional_state=create_neutral_emotional_state(),
            emotional_decay_rate=emotional_decay_rate,
        )

        # Initialize ConsistencyValidator
        self.enable_validation = enable_validation
        if enable_validation:
            self.consistency_validator = ConsistencyValidator(
                llm_client=self.llm_client,
                core_identity=self.core_identity,
                config=ValidationConfig(
                    min_overall_score=0.7,
                    max_attempts=2,
                ),
            )
        else:
            self.consistency_validator = None

        # Initialize AdaptiveUserModeling
        self.enable_user_modeling = enable_user_modeling
        if enable_user_modeling:
            self.user_modeling = AdaptiveUserModeling(
                llm_client=self.llm_client,
                storage=InMemoryUserModelStorage(),
            )
        else:
            self.user_modeling = None

        # Track current emotional state
        self.current_emotional_state: EmotionalState = create_neutral_emotional_state()

        # Track last interaction time for emotional decay
        self.last_interaction_time: float = 0.0

    async def chat(
        self,
        user_input: str,
        stream: bool = False,
    ) -> str | AsyncIterator[str]:
        """Process user input and generate response.

        This method uses the new architecture when enabled:
        1. Updates emotional state with time decay
        2. Processes through cognitive-emotional engine
        3. Retrieves relevant memories from all layers
        4. Builds three-layer prompt with RoleRAG
        5. Validates response for consistency
        6. Updates user model with interaction

        Args:
            user_input: User's message
            stream: Whether to stream the response

        Returns:
            Response string or async iterator for streaming
        """
        if not self.llm_client:
            raise RuntimeError("LLM client not configured")

        if not self.use_new_architecture:
            # Fall back to legacy implementation
            return await self._legacy_chat(user_input, stream)

        try:
            # Step 1: Try skills first (legacy compatibility)
            skill_result = await self._try_skills(user_input)
            if skill_result:
                return skill_result

            # Step 2: Update user model if enabled
            if self.user_modeling:
                await self._update_user_model(user_input)

            # Step 3: Process through cognitive-emotional engine
            fused_state = await self._process_cognitive_emotional(user_input)
            self.current_emotional_state = fused_state.fused_emotional_state

            # Step 4: Build dynamic context
            dynamic_context = self._build_dynamic_context(fused_state)

            # Step 5: Store in working memory
            self.hierarchical_memory.working.add_exchange("user", user_input)

            # Step 6: Retrieve relevant memories
            memory_context = await self.hierarchical_memory.retrieve(
                query=user_input,
                context={
                    "session_id": self.session_id,
                    "include_working": True,
                },
            )

            # Step 7: Build three-layer prompt with RoleRAG
            task_context = TaskContext(
                task_type="conversation",
                instructions=fused_state.response_guidance,
            )

            layered_prompt = await self.prompt_engine.build_prompt(
                user_input=user_input,
                dynamic_context=dynamic_context,
                task_context=task_context,
            )

            # Step 8: Build messages
            messages = self._build_messages(layered_prompt, memory_context)

            # Step 9: Generate response
            if stream:
                return self._stream_response_new_architecture(messages, user_input)
            else:
                response = await self._generate_and_validate(messages, user_input)
                return response

        except Exception as e:
            logger.error(f"Error in new architecture chat: {e}")
            # Fall back to legacy mode on error
            logger.warning("Falling back to legacy chat due to error")
            return await self._legacy_chat(user_input, stream)

    async def _try_skills(self, user_input: str) -> str | None:
        """Try to execute matching skills."""
        skill_context = SkillContext(
            user_input=user_input,
            conversation_history=[],
            current_mood=self.current_emotional_state.primary_emotion,
            session_id=self.session_id,
            memory_store=self.memory_store,
            persona_manager=self.persona_manager,
        )

        skill_result = await self.skill_registry.execute_matching(skill_context)
        if skill_result and skill_result.success and skill_result.response:
            # Store in hierarchical memory
            await self.hierarchical_memory.store_exchange(
                user_msg=user_input,
                assistant_msg=skill_result.response,
                importance=0.5,
            )
            return skill_result.response

        return None

    async def _update_user_model(self, user_input: str) -> None:
        """Update user model with interaction."""
        if not self.user_modeling:
            return

        try:
            await self.user_modeling.update_from_interaction(
                user_id=self.session_id,
                user_message=user_input,
                assistant_message="",  # Will be updated after response
                emotional_state=self.current_emotional_state,
            )
        except Exception as e:
            logger.warning(f"Failed to update user model: {e}")

    async def _process_cognitive_emotional(self, user_input: str):
        """Process input through cognitive-emotional engine."""
        return await self.cognitive_emotional_engine.process(
            user_input=user_input,
            working_memory=self.hierarchical_memory.working,
        )

    def _build_dynamic_context(self, fused_state) -> DynamicContext:
        """Build dynamic context from fused state."""
        # Get relationship state from user modeling if available
        if self.user_modeling:
            try:
                user_model = self.user_modeling.storage.get_sync(self.session_id)
                if user_model:
                    relationship = {
                        "intimacy": user_model.intimacy_level,
                        "trust": user_model.trust_level,
                        "respect": 0.5,
                        "familiarity": user_model.familiarity,
                        "current_stage": "established"
                        if user_model.interaction_count > 10
                        else "developing",
                        "interaction_count": user_model.interaction_count,
                    }
                else:
                    relationship = {}
            except Exception:
                relationship = {}
        else:
            relationship = {}

        return DynamicContext(
            emotional=fused_state.fused_emotional_state,
            social=relationship,
            cognitive={
                "focus_target": "user",
                "attention_level": 0.8,
                "active_goals": [],
                "current_intention": "respond_helpfully",
                "cognitive_load": 0.3,
            },
            conversation_turn=self.hierarchical_memory.working.exchange_count,
            topic=fused_state.cognitive.topics[0] if fused_state.cognitive.topics else "",
            user_intent=fused_state.cognitive.user_intent,
        )

    def _build_messages(
        self,
        layered_prompt,
        memory_context,
    ) -> list[dict[str, str]]:
        """Build messages for LLM."""
        # Get system prompt from layered prompt
        system_prompt = layered_prompt.to_system_prompt()

        # Add memory context
        memory_text = memory_context.to_prompt_context()
        if memory_text:
            system_prompt += f"\n\n## Relevant Context\n{memory_text}"

        messages = [{"role": "system", "content": system_prompt}]

        # Add working memory exchanges
        for msg in memory_context.working_messages[-5:]:  # Last 5 exchanges
            messages.append({"role": msg.role, "content": msg.content})

        return messages

    async def _generate_and_validate(self, messages: list, user_input: str) -> str:
        """Generate response with optional validation."""
        # Generate initial response
        response_obj = await self.llm_client.chat(messages)
        response = response_obj.content

        # Validate if enabled
        if self.consistency_validator and self.enable_validation:
            try:
                dynamic_context = self._build_dynamic_context(
                    await self._process_cognitive_emotional(user_input)
                )

                (
                    validated_response,
                    reports,
                ) = await self.consistency_validator.validate_with_regeneration(
                    initial_response=response,
                    dynamic_context=dynamic_context,
                    conversation_history=[],
                    max_attempts=2,
                )

                # Log validation results
                if reports:
                    final_report = reports[-1]
                    logger.debug(
                        f"Validation score: {final_report.overall_score:.2f}, "
                        f"passed: {final_report.passed}"
                    )

                response = validated_response

            except Exception as e:
                logger.warning(f"Validation failed, using original response: {e}")

        # Apply style
        styled = self._apply_style(response)

        # Store exchange
        await self._store_exchange(user_input, styled)

        return styled

    async def _stream_response_new_architecture(
        self,
        messages: list[dict[str, str]],
        user_input: str,
    ) -> AsyncIterator[str]:
        """Stream response using new architecture."""
        full_response = []

        async for chunk in self.llm_client.chat_stream(messages):
            full_response.append(chunk)
            yield chunk

        # Store complete response
        complete = "".join(full_response)
        styled = self._apply_style(complete)
        await self._store_exchange(user_input, styled)

    async def _store_exchange(self, user_msg: str, assistant_msg: str) -> None:
        """Store conversation exchange in both legacy and new memory systems."""
        # Store in legacy memory
        await self.memory_store.store(
            session_id=self.session_id,
            user_message=user_msg,
            assistant_message=assistant_msg,
        )

        # Store in hierarchical memory
        await self.hierarchical_memory.store_exchange(
            user_msg=user_msg,
            assistant_msg=assistant_msg,
            importance=0.5,
        )

        # Update user model with complete interaction
        if self.user_modeling:
            try:
                await self.user_modeling.update_from_interaction(
                    user_id=self.session_id,
                    user_message=user_msg,
                    assistant_message=assistant_msg,
                    emotional_state=self.current_emotional_state,
                )
            except Exception as e:
                logger.warning(f"Failed to update user model with response: {e}")

    async def _legacy_chat(self, user_input: str, stream: bool = False) -> str | AsyncIterator[str]:
        """Legacy chat implementation for backward compatibility."""
        # Try skills first
        skill_context = SkillContext(
            user_input=user_input,
            conversation_history=[],
            current_mood=self.persona_manager.get_mood_engine().current_state.name,
            session_id=self.session_id,
            memory_store=self.memory_store,
            persona_manager=self.persona_manager,
        )

        skill_result = await self.skill_registry.execute_matching(skill_context)
        if skill_result and skill_result.success and skill_result.response:
            await self._store_exchange(user_input, skill_result.response)
            return skill_result.response

        # Update mood
        self.persona_manager.update_mood(user_input)

        # Build system prompt
        system_prompt = self.persona_manager.build_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]

        # Add recent memories
        memories = await self.memory_store.retrieve_recent(self.session_id, limit=10)
        for memory in memories:
            messages.append({"role": "user", "content": memory.user_message})
            messages.append({"role": "assistant", "content": memory.assistant_message})

        # Add current input
        messages.append({"role": "user", "content": user_input})

        # Generate response
        if stream:
            return self._legacy_stream_response(messages)
        else:
            response = await self.llm_client.chat(messages)
            styled = self._apply_style(response.content)
            await self._store_exchange(user_input, styled)
            return styled

    async def _legacy_stream_response(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        """Legacy stream response."""
        full_response = []

        async for chunk in self.llm_client.chat_stream(messages):
            full_response.append(chunk)
            yield chunk

        complete = "".join(full_response)
        styled = self._apply_style(complete)
        await self._store_exchange(messages[-1]["content"], styled)

    def _apply_style(self, text: str) -> str:
        """Apply linguistic style to response."""
        return self.persona_manager.apply_linguistic_style(
            text,
            use_kaomoji=True,
            use_nickname=True,
        )

    def get_session_info(self) -> dict[str, Any]:
        """Get session information including new architecture state."""
        info = {
            "session_id": self.session_id,
            "use_new_architecture": self.use_new_architecture,
        }

        if self.use_new_architecture:
            info.update(
                {
                    "character": self.core_identity.name,
                    "current_emotion": self.current_emotional_state.primary_emotion,
                    "emotional_valence": self.current_emotional_state.valence,
                    "emotional_arousal": self.current_emotional_state.arousal,
                    "validation_enabled": self.enable_validation,
                    "user_modeling_enabled": self.enable_user_modeling,
                    "memory_stats": self.hierarchical_memory.get_stats(),
                }
            )
        else:
            char = self.persona_manager.get_character()
            mood_engine = self.persona_manager.get_mood_engine()
            info.update(
                {
                    "character": char.name if char else None,
                    "current_mood": mood_engine.current_state.name if mood_engine else None,
                }
            )

        return info


# Backward compatibility alias
AgentEngine = NewArchitectureAgentEngine

__all__ = ["NewArchitectureAgentEngine", "AgentEngine"]
