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
from persona_agent.core.planning import (
    ExecutionConfig,
    PlanExecutor,
    PlanningConfig,
    PlanningEngine,
)
from persona_agent.core.planning.models import Plan
from persona_agent.mcp.client import MCPClient, get_mcp_client
from persona_agent.skills.base import SkillContext
from persona_agent.skills.registry import SkillRegistry, get_registry
from persona_agent.tools.base import ToolContext
from persona_agent.tools.discovery import ToolRegistry, get_default_registry
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
        planning_config: PlanningConfig | None = None,
        execution_config: ExecutionConfig | None = None,
        tool_registry: ToolRegistry | None = None,
        enable_tools: bool = True,
    ):
        """Initialize agent engine.

        Args:
            persona_manager: Persona manager instance
            memory_store: Memory store instance
            llm_client: LLM client instance
            session_id: Session identifier
            skill_registry: Skill registry for executing skills
            mcp_client: MCP client for tool execution
            planning_config: Configuration for the planning system
            execution_config: Configuration for plan execution
            tool_registry: Tool registry for managing tools
            enable_tools: Whether to enable tool functionality
        """
        self.persona_manager = persona_manager or PersonaManager()
        self.memory_store = memory_store or MemoryStore()
        self.llm_client = llm_client
        self.session_id = session_id or str(uuid.uuid4())
        self.skill_registry = skill_registry or get_registry()
        self.mcp_client = mcp_client or get_mcp_client(memory_store=self.memory_store)

        # Tool system
        self.enable_tools = enable_tools
        self.tool_registry = tool_registry or get_default_registry() if enable_tools else None

        # Planning system
        self.planning_config = planning_config or PlanningConfig()
        self.execution_config = execution_config or ExecutionConfig()
        self.planning_engine = PlanningEngine(self, self.planning_config)
        self.plan_executor = PlanExecutor(self, self.execution_config)
        self._active_plans: dict[str, Plan] = {}

        logger.info(f"AgentEngine initialized (session: {self.session_id})")

    async def chat(
        self,
        user_input: str,
        stream: bool = False,
        enable_planning: bool = True,
        on_plan_progress: Any = None,
    ) -> str | AsyncIterator[str]:
        """Process user input and generate response.

        Args:
            user_input: User's message
            stream: Whether to stream the response
            enable_planning: Whether to use planning for complex tasks
            on_plan_progress: Optional callback for plan execution progress

        Returns:
            Response string or async iterator for streaming
        """
        if not self.llm_client:
            raise RuntimeError("LLM client not configured")

        # Try skills first
        mood_engine = self.persona_manager.get_mood_engine()
        skill_context = SkillContext(
            user_input=user_input,
            conversation_history=[],
            current_mood=mood_engine.current_state.name if mood_engine else "neutral",
            session_id=self.session_id,
            memory_store=self.memory_store,
            persona_manager=self.persona_manager,
        )

        skill_result = await self.skill_registry.execute_matching(skill_context)
        if skill_result and skill_result.success and skill_result.response:
            # Store the exchange
            await self._store_exchange(user_input, skill_result.response)
            return skill_result.response

        # Check if planning is needed
        if enable_planning and await self.planning_engine.should_plan(user_input):
            return await self._handle_with_planning(user_input, on_plan_progress)

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

    async def _handle_with_planning(
        self,
        user_input: str,
        on_progress: Any = None,
    ) -> str:
        """Handle user input using the planning system.

        Args:
            user_input: User's request
            on_progress: Optional progress callback

        Returns:
            Formatted response with plan results
        """
        logger.info(f"Using planning system for: {user_input[:50]}...")

        # Create plan
        context = {
            "current_persona": self.get_current_persona(),
            "session_id": self.session_id,
        }
        plan = await self.planning_engine.create_plan(user_input, context)
        self._active_plans[plan.id] = plan

        try:
            # Execute plan
            results = await self.plan_executor.execute_plan(
                plan,
                on_progress=on_progress,
            )

            # Format response
            return self._format_plan_results(results)

        except Exception as e:
            logger.error(f"Plan execution failed: {e}")
            return f"I encountered an error while working on your request: {e}"

        finally:
            del self._active_plans[plan.id]

    def _format_plan_results(self, results: dict[str, Any]) -> str:
        """Format plan execution results for user."""
        status = results.get("status", "unknown")

        if status == "completed":
            lines = ["I've completed your request. Here's what I did:"]

            for task_id in results.get("completed_tasks", []):
                output = results.get("outputs", {}).get(task_id, "")
                if output:
                    lines.append(f"\n**{task_id}**: {output[:300]}")

            return "\n".join(lines)

        elif status == "failed":
            lines = ["I encountered some issues while working on your request:"]

            for task_id in results.get("completed_tasks", []):
                output = results.get("outputs", {}).get(task_id, "")
                if output:
                    lines.append(f"✓ {task_id}: {output[:200]}...")

            for task_id in results.get("failed_tasks", []):
                error = results.get("outputs", {}).get(task_id, "Unknown error")
                lines.append(f"✗ {task_id}: {error[:100]}")

            return "\n".join(lines)

        else:
            return "Plan execution ended with unknown status."

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

    def get_available_tools(self) -> list[dict[str, Any]]:
        """Get list of available tools formatted for LLM.

        Returns:
            List of tool schemas in OpenAI format
        """
        if not self.tool_registry:
            return []
        return self.tool_registry.get_all_schemas_for_llm("openai")

    async def execute_tool(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool with given parameters.

        Args:
            tool_name: Name of the tool to execute
            params: Tool parameters

        Returns:
            Tool execution result as dict
        """
        if not self.tool_registry:
            return {"success": False, "error": "Tools not enabled"}

        tool = self.tool_registry.get_tool(tool_name)
        if not tool:
            return {"success": False, "error": f"Tool '{tool_name}' not found"}

        # Create tool context
        context = ToolContext(
            user_id="user",  # Could be extracted from session
            session_id=self.session_id,
            memory_store=self.memory_store,
        )

        try:
            result = await tool.execute(context, **params)
            return result.to_dict()
        except Exception as e:
            logger.exception(f"Tool execution failed: {tool_name}")
            return {"success": False, "error": str(e)}

    def list_tools(self) -> list[dict[str, Any]]:
        """List all available tools with their metadata.

        Returns:
            List of tool metadata dicts
        """
        if not self.tool_registry:
            return []

        tools = self.tool_registry.list_tools()
        return [t.to_dict() for t in tools]
