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
from persona_agent.core.pipeline import ChatContext, ChatPipeline
from persona_agent.core.pipeline.stages import (
    CleanupStage,
    ContextPreparationStage,
    MemoryStorageStage,
    PlanningExecutionStage,
    ResponseGenerationStage,
    SkillExecutionStage,
    ValidationStage,
)
from persona_agent.core.planning import (
    ExecutionConfig,
    PlanExecutor,
    PlanningConfig,
    PlanningEngine,
)
from persona_agent.core.planning.models import Plan
from persona_agent.mcp.client import MCPClient, get_mcp_client
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
        pipeline: ChatPipeline | None = None,
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
            pipeline: Optional custom chat pipeline (uses default if not provided)
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

        # Pipeline (injected or built with defaults)
        self.pipeline = pipeline or self._build_default_pipeline()

        logger.info(f"AgentEngine initialized (session: {self.session_id})")

    def _build_default_pipeline(self) -> ChatPipeline:
        """Build the default chat pipeline with all standard stages."""
        return ChatPipeline(
            stages=[
                ValidationStage(self.llm_client),
                SkillExecutionStage(
                    self.skill_registry,
                    self.persona_manager,
                    self.memory_store,
                ),
                PlanningExecutionStage(
                    self.planning_engine,
                    self.plan_executor,
                ),
                ContextPreparationStage(
                    self.persona_manager,
                    self.memory_store,
                ),
                ResponseGenerationStage(
                    self.llm_client,  # type: ignore[arg-type]
                    self.persona_manager,
                    self.memory_store,
                ),
                MemoryStorageStage(self.memory_store),
            ],
            cleanup_stage=CleanupStage(),
        )

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
        if self.pipeline is None:
            self.pipeline = self._build_default_pipeline()

        context = ChatContext(
            user_input=user_input,
            session_id=self.session_id,
            stream=stream,
            enable_planning=enable_planning,
            on_plan_progress=on_plan_progress,
        )

        result = await self.pipeline.execute(context)
        if result.response is None:
            raise RuntimeError("Pipeline did not produce a response")
        return result.response

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
