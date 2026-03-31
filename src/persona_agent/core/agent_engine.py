"""Main agent engine for persona-agent.

Coordinates all components to provide a unified interface for
role-playing conversations.
"""

import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from persona_agent.core.memory_store import MemoryStore
from persona_agent.core.persona_manager import PersonaManager
from persona_agent.mcp.client import MCPClient, get_mcp_client
from persona_agent.skills.base import SkillContext
from persona_agent.skills.registry import SkillRegistry, get_registry
from persona_agent.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


class AgentEngine:
    """Main agent engine coordinating all components."""

    def __init__(
        self,
        persona_manager: PersonaManager | None = None,
        memory_store: MemoryStore | None = None,
        llm_client: LLMClient | None = None,
        session_id: str | None = None,
        skill_registry: SkillRegistry | None = None,
        mcp_client: MCPClient | None = None,
    ):
        """Initialize agent engine.

        Args:
            persona_manager: Persona manager instance
            memory_store: Memory store instance
            llm_client: LLM client instance
            session_id: Session identifier
            skill_registry: Skill registry for executing skills
            mcp_client: MCP client for tool execution
        """
        self.persona_manager = persona_manager or PersonaManager()
        self.memory_store = memory_store or MemoryStore()
        self.llm_client = llm_client
        self.session_id = session_id or str(uuid.uuid4())
        self.skill_registry = skill_registry or get_registry()
        self.mcp_client = mcp_client or get_mcp_client(memory_store=self.memory_store)

        logger.info(f"AgentEngine initialized (session: {self.session_id})")

    async def chat(
        self,
        user_input: str,
        stream: bool = False,
    ) -> str | AsyncIterator[str]:
        """Process user input and generate response.

        Args:
            user_input: User's message
            stream: Whether to stream the response

        Returns:
            Response string or async iterator for streaming
        """
        if not self.llm_client:
            raise RuntimeError("LLM client not configured")

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
            # Store the exchange
            await self._store_exchange(user_input, skill_result.response)
            return skill_result.response

        # Update mood based on input
        self.persona_manager.update_mood(user_input)

        # Build system prompt
        system_prompt = self.persona_manager.build_system_prompt()

        # Build messages
        messages = [{"role": "system", "content": system_prompt}]

        # Add relevant memories (simplified - just recent)
        memories = await self.memory_store.retrieve_recent(self.session_id, limit=10)
        for memory in memories:
            messages.append({"role": "user", "content": memory.user_message})
            messages.append({"role": "assistant", "content": memory.assistant_message})

        # Add current input
        messages.append({"role": "user", "content": user_input})

        # Generate response
        if stream:
            return self._stream_response(messages)
        else:
            response = await self.llm_client.chat(messages)
            styled = self._apply_style(response.content)
            await self._store_exchange(user_input, styled)
            return styled

    async def _stream_response(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        """Stream response from LLM.

        Args:
            messages: Message list

        Yields:
            Response chunks
        """
        full_response = []

        async for chunk in self.llm_client.chat_stream(messages):
            full_response.append(chunk)
            yield chunk

        # Store complete response
        complete = "".join(full_response)
        styled = self._apply_style(complete)
        await self._store_exchange(messages[-1]["content"], styled)

    def _apply_style(self, text: str) -> str:
        """Apply linguistic style to response.

        Args:
            text: Base response text

        Returns:
            Styled text
        """
        return self.persona_manager.apply_linguistic_style(
            text,
            use_kaomoji=True,
            use_nickname=True,
        )

    async def _store_exchange(self, user_msg: str, assistant_msg: str) -> None:
        """Store conversation exchange.

        Args:
            user_msg: User message
            assistant_msg: Assistant response
        """
        await self.memory_store.store(
            session_id=self.session_id,
            user_message=user_msg,
            assistant_message=assistant_msg,
        )

    def switch_persona(self, character_name: str) -> None:
        """Switch to a different character.

        Args:
            character_name: Name of character to switch to
        """
        self.persona_manager.load_character(character_name)
        logger.info(f"Switched to persona: {character_name}")

    def get_current_persona(self) -> str | None:
        """Get current persona name.

        Returns:
            Persona name or None
        """
        char = self.persona_manager.get_character()
        return char.name if char else None

    def get_session_info(self) -> dict[str, Any]:
        """Get session information.

        Returns:
            Session info dict
        """
        char = self.persona_manager.get_character()
        mood_engine = self.persona_manager.get_mood_engine()

        return {
            "session_id": self.session_id,
            "character": char.name if char else None,
            "current_mood": mood_engine.current_state.name if mood_engine else None,
        }
