# AgentEngine Pipeline Extraction - Implementation Plan

## Executive Summary

Extract AgentEngine's monolithic `chat()` method (367 lines) into 7 independent pipeline stages with a configurable orchestrator. Each stage has a single responsibility, is independently testable via dependency injection, and integrates with the existing DI container.

**Target reduction**: AgentEngine from 367 lines to ~150 lines (chat logic extracted).

**Backward compatibility**: 100% preserved - `AgentEngine.chat()` signature and behavior remain identical.

---

## 1. Stage Interface Design

### 1.1 Core Abstractions

```python
# src/persona_agent/core/pipeline/context.py
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class ChatContext:
    """Mutable context object passed between pipeline stages.
    
    Carries all state needed throughout the chat flow.
    Stages mutate this context in-place and return it via StageResult.
    """
    # Input parameters (set once at pipeline start)
    user_input: str
    session_id: str
    stream: bool = False
    enable_planning: bool = True
    on_plan_progress: Any = None
    
    # Mutable state (modified by stages)
    correlation_id: str | None = None
    messages: list[dict[str, str]] = field(default_factory=list)
    response: str | AsyncIterator[str] | None = None
    is_complete: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StageResult:
    """Result from a pipeline stage execution.
    
    should_continue=False signals pipeline short-circuit.
    This allows skill matching and planning to exit early.
    """
    context: ChatContext
    should_continue: bool = True
```

```python
# src/persona_agent/core/pipeline/stage.py
from typing import Protocol
from persona_agent.core.pipeline.context import ChatContext, StageResult


class PipelineStage(Protocol):
    """Protocol for chat pipeline stages.
    
    Each stage implements a single responsibility in the chat flow.
    Stages are composable, testable, and configurable.
    """
    
    async def process(self, context: ChatContext) -> StageResult:
        """Execute this stage's logic.
        
        Args:
            context: Current pipeline context with all accumulated state
            
        Returns:
            StageResult containing updated context and continuation flag.
            Set should_continue=False to short-circuit the pipeline.
        """
        ...
```

### 1.2 Design Rationale

- **Mutable context**: Chosen over immutable `.replace()` for simplicity and to match existing codebase patterns (SkillContext, ToolContext are mutable). This avoids excessive object churn in a hot path.
- **Protocol over ABC**: Allows both classes and callables. The existing DI container's `autowire()` works with class-based stages.
- **Explicit short-circuit**: `StageResult.should_continue` makes control flow visible and testable, rather than relying on sentinel values or exceptions.

---

## 2. Pipeline Orchestrator

```python
# src/persona_agent/core/pipeline/pipeline.py
import logging
from persona_agent.core.pipeline.context import ChatContext, StageResult
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
                    logger.debug(
                        f"Pipeline short-circuited by {stage.__class__.__name__}"
                    )
                    break
                    
        except Exception as e:
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
```

### 2.1 Orchestrator Design Decisions

- **Sequential execution**: The chat flow is inherently sequential (skills -> planning -> mood -> prompt -> memories -> generation). No need for DAG parallelism.
- **Cleanup in finally**: Matches original `chat()` behavior where `clear_correlation_id()` runs in `finally`.
- **Exception isolation for cleanup**: Cleanup errors are logged but don't mask the original exception.

---

## 3. Pipeline Stages Breakdown

### Stage 1: ValidationStage
**Responsibility**: Initialize tracing context and validate prerequisites.

```python
# src/persona_agent/core/pipeline/stages/validation.py
import uuid
from persona_agent.core.pipeline.context import ChatContext, StageResult
from persona_agent.core.pipeline.stage import PipelineStage
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
```

**Extracted from**: `AgentEngine.chat()` lines 103-108
**Dependencies**: LLMClient
**Short-circuits**: No (raises on invalid state)

---

### Stage 2: SkillExecutionStage
**Responsibility**: Attempt skill-based handling before falling back to LLM.

```python
# src/persona_agent/core/pipeline/stages/skill_execution.py
from persona_agent.core.pipeline.context import ChatContext, StageResult
from persona_agent.core.memory_store import MemoryStore
from persona_agent.core.persona_manager import PersonaManager
from persona_agent.skills.registry import SkillRegistry
from persona_agent.skills.base import SkillContext


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
```

**Extracted from**: `AgentEngine.chat()` lines 110-125
**Dependencies**: SkillRegistry, PersonaManager, MemoryStore
**Short-circuits**: Yes, when skill handles the request

---

### Stage 3: PlanningExecutionStage
**Responsibility**: Handle complex multi-step requests via planning system.

```python
# src/persona_agent/core/pipeline/stages/planning.py
import logging
from typing import Any
from persona_agent.core.pipeline.context import ChatContext, StageResult
from persona_agent.core.planning.engine import PlanningEngine
from persona_agent.core.planning.executor import PlanExecutor
from persona_agent.core.planning.models import Plan

logger = logging.getLogger(__name__)


class PlanningExecutionStage:
    """Handles complex requests using the planning system.
    
    If planning is enabled and the input requires multi-step execution,
    creates a plan, executes it, and formats results. Short-circuits
    the normal chat flow.
    """
    
    def __init__(
        self,
        planning_engine: PlanningEngine,
        plan_executor: PlanExecutor,
    ):
        self.planning_engine = planning_engine
        self.plan_executor = plan_executor
        self._active_plans: dict[str, Plan] = {}
    
    async def process(self, context: ChatContext) -> StageResult:
        if not context.enable_planning:
            return StageResult(context, should_continue=True)
        
        if not await self.planning_engine.should_plan(context.user_input):
            return StageResult(context, should_continue=True)
        
        # Execute planning flow
        response = await self._execute_planning(context)
        context.response = response
        context.is_complete = True
        return StageResult(context, should_continue=False)
    
    async def _execute_planning(self, context: ChatContext) -> str:
        """Internal planning execution logic."""
        logger.info(f"Using planning system for: {context.user_input[:50]}...")
        
        # Note: This needs access to get_current_persona() which is 
        # currently on AgentEngine. We'll inject it or use persona_manager.
        plan_context = {
            "session_id": context.session_id,
            # "current_persona": persona_manager reference needed
        }
        
        plan = await self.planning_engine.create_plan(
            context.user_input, plan_context
        )
        self._active_plans[plan.id] = plan
        
        try:
            results = await self.plan_executor.execute_plan(
                plan,
                on_progress=context.on_plan_progress,
            )
            return self._format_results(results)
        except Exception as e:
            logger.error(f"Plan execution failed: {e}")
            return f"I encountered an error while working on your request: {e}"
        finally:
            del self._active_plans[plan.id]
    
    def _format_results(self, results: dict[str, Any]) -> str:
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
        
        return "Plan execution ended with unknown status."
```

**Extracted from**: `AgentEngine._handle_with_planning()` and planning check in `chat()`
**Dependencies**: PlanningEngine, PlanExecutor
**Short-circuits**: Yes, when planning is used
**Note**: The `_format_results` method is extracted from `_format_plan_results()`. The `_active_plans` tracking moves here.

---

### Stage 4: ContextPreparationStage
**Responsibility**: Build conversation context (mood, prompt, memories, messages).

```python
# src/persona_agent/core/pipeline/stages/context_prep.py
from persona_agent.core.pipeline.context import ChatContext, StageResult
from persona_agent.core.memory_store import MemoryStore
from persona_agent.core.persona_manager import PersonaManager


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
        # Update mood based on input
        self.persona_manager.update_mood(context.user_input)
        
        # Build system prompt
        system_prompt = self.persona_manager.build_system_prompt()
        context.messages = [{"role": "system", "content": system_prompt}]
        
        # Retrieve recent memories
        memories = await self.memory_store.retrieve_recent(
            context.session_id, limit=self.memory_limit
        )
        for memory in memories:
            context.messages.append({"role": "user", "content": memory.user_message})
            context.messages.append(
                {"role": "assistant", "content": memory.assistant_message}
            )
        
        # Add current input
        context.messages.append({"role": "user", "content": context.user_input})
        
        return StageResult(context, should_continue=True)
```

**Extracted from**: `AgentEngine.chat()` lines 131-147
**Dependencies**: PersonaManager, MemoryStore
**Short-circuits**: No

---

### Stage 5: ResponseGenerationStage
**Responsibility**: Generate response via LLM (streaming or normal) and apply style.

```python
# src/persona_agent/core/pipeline/stages/generation.py
from collections.abc import AsyncIterator
from persona_agent.core.pipeline.context import ChatContext, StageResult
from persona_agent.core.memory_store import MemoryStore
from persona_agent.core.persona_manager import PersonaManager
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
        
        # Non-streaming path
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
            
            # After stream completes, apply style and store
            complete = "".join(full_response)
            styled = self._apply_style(complete)
            
            await self.memory_store.store(
                session_id=context.session_id,
                user_message=context.user_input,
                assistant_message=styled,
            )
            # Update context for consistency
            context.response = styled
        
        return _stream()
```

**Extracted from**: `AgentEngine.chat()` lines 149-156 and `_stream_response()` lines 232-253
**Dependencies**: LLMClient, PersonaManager, MemoryStore
**Short-circuits**: Yes, for streaming (memory storage deferred to iterator consumption)

---

### Stage 6: MemoryStorageStage
**Responsibility**: Persist non-streaming conversation exchanges to memory.

```python
# src/persona_agent/core/pipeline/stages/memory_store.py
from persona_agent.core.pipeline.context import ChatContext, StageResult
from persona_agent.core.memory_store import MemoryStore


class MemoryStorageStage:
    """Stores the conversation exchange in memory.
    
    Only stores for non-streaming responses. Streaming responses
    handle storage internally via the async iterator wrapper.
    """
    
    def __init__(self, memory_store: MemoryStore):
        self.memory_store = memory_store
    
    async def process(self, context: ChatContext) -> StageResult:
        if context.stream:
            # Streaming handles storage in the iterator wrapper
            return StageResult(context, should_continue=True)
        
        if context.response and isinstance(context.response, str):
            await self.memory_store.store(
                session_id=context.session_id,
                user_message=context.user_input,
                assistant_message=context.response,
            )
        
        return StageResult(context, should_continue=True)
```

**Extracted from**: `AgentEngine._store_exchange()` and storage logic in `chat()`
**Dependencies**: MemoryStore
**Short-circuits**: No

---

### Stage 7: CleanupStage
**Responsibility**: Always-run cleanup (correlation ID clearing).

```python
# src/persona_agent/core/pipeline/stages/cleanup.py
from persona_agent.core.pipeline.context import ChatContext, StageResult
from persona_agent.utils.logging_config import clear_correlation_id


class CleanupStage:
    """Cleans up resources after pipeline execution.
    
    This stage runs in the finally block of the pipeline,
    ensuring cleanup happens even if earlier stages fail.
    """
    
    async def process(self, context: ChatContext) -> StageResult:
        clear_correlation_id()
        return StageResult(context, should_continue=True)
```

**Extracted from**: `AgentEngine.chat()` finally block line 158
**Dependencies**: None
**Short-circuits**: No
**Special**: Runs in `finally` block of ChatPipeline.execute()

---

## 4. Integration with AgentEngine

### 4.1 Refactored AgentEngine

```python
# src/persona_agent/core/agent_engine.py (refactored)
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from persona_agent.core.memory_store import MemoryStore
from persona_agent.core.persona_manager import PersonaManager
from persona_agent.core.planning import (
    ExecutionConfig,
    PlanningConfig,
    PlanningEngine,
)
from persona_agent.core.planning.executor import PlanExecutor
from persona_agent.core.pipeline.pipeline import ChatPipeline
from persona_agent.core.pipeline.context import ChatContext
from persona_agent.core.pipeline.stages.validation import ValidationStage
from persona_agent.core.pipeline.stages.skill_execution import SkillExecutionStage
from persona_agent.core.pipeline.stages.planning import PlanningExecutionStage
from persona_agent.core.pipeline.stages.context_prep import ContextPreparationStage
from persona_agent.core.pipeline.stages.generation import ResponseGenerationStage
from persona_agent.core.pipeline.stages.memory_store import MemoryStorageStage
from persona_agent.core.pipeline.stages.cleanup import CleanupStage
from persona_agent.mcp.client import MCPClient, get_mcp_client
from persona_agent.skills.registry import SkillRegistry, get_registry
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
        self.persona_manager = persona_manager or PersonaManager()
        self.memory_store = memory_store or MemoryStore()
        self.llm_client = llm_client
        self.session_id = session_id or str(uuid.uuid4())
        self.skill_registry = skill_registry or get_registry()
        self.mcp_client = mcp_client or get_mcp_client(memory_store=self.memory_store)

        self.enable_tools = enable_tools
        self.tool_registry = tool_registry or get_default_registry() if enable_tools else None

        # Planning system
        self.planning_config = planning_config or PlanningConfig()
        self.execution_config = execution_config or ExecutionConfig()
        self.planning_engine = PlanningEngine(self, self.planning_config)
        self.plan_executor = PlanExecutor(self, self.execution_config)

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
                    self.llm_client,
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
        
        Backward-compatible interface - delegates to configurable pipeline.
        """
        context = ChatContext(
            user_input=user_input,
            session_id=self.session_id,
            stream=stream,
            enable_planning=enable_planning,
            on_plan_progress=on_plan_progress,
        )
        
        result = await self.pipeline.execute(context)
        return result.response

    # Persona management methods remain unchanged
    def switch_persona(self, character_name: str) -> None:
        self.persona_manager.load_character(character_name)
        logger.info(f"Switched to persona: {character_name}")

    def get_current_persona(self) -> str | None:
        char = self.persona_manager.get_character()
        return char.name if char else None

    def get_session_info(self) -> dict[str, Any]:
        char = self.persona_manager.get_character()
        mood_engine = self.persona_manager.get_mood_engine()
        return {
            "session_id": self.session_id,
            "character": char.name if char else None,
            "current_mood": mood_engine.current_state.name if mood_engine else None,
        }

    # Tool management methods remain unchanged
    def get_available_tools(self) -> list[dict[str, Any]]:
        if not self.tool_registry:
            return []
        return self.tool_registry.get_all_schemas_for_llm("openai")

    async def execute_tool(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.tool_registry:
            return {"success": False, "error": "Tools not enabled"}
        
        tool = self.tool_registry.get_tool(tool_name)
        if not tool:
            return {"success": False, "error": f"Tool '{tool_name}' not found"}
        
        from persona_agent.tools.base import ToolContext
        context = ToolContext(
            user_id="user",
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
        if not self.tool_registry:
            return []
        tools = self.tool_registry.list_tools()
        return [t.to_dict() for t in tools]
```

### 4.2 DI Container Registration

```python
# Example: Registering pipeline in DI container
from persona_agent.core.container import Container

container = Container()

# Register individual stages
container.register(ValidationStage, ValidationStage)
container.register(SkillExecutionStage, SkillExecutionStage)
container.register(PlanningExecutionStage, PlanningExecutionStage)
container.register(ContextPreparationStage, ContextPreparationStage)
container.register(ResponseGenerationStage, ResponseGenerationStage)
container.register(MemoryStorageStage, MemoryStorageStage)
container.register(CleanupStage, CleanupStage)

# Register pipeline factory
container.register(ChatPipeline, lambda: ChatPipeline(
    stages=[
        container.autowire(ValidationStage),
        container.autowire(SkillExecutionStage),
        container.autowire(PlanningExecutionStage),
        container.autowire(ContextPreparationStage),
        container.autowire(ResponseGenerationStage),
        container.autowire(MemoryStorageStage),
    ],
    cleanup_stage=container.autowire(CleanupStage),
))
```

### 4.3 Backward Compatibility Notes

- **Exact same `chat()` signature**: All parameters preserved.
- **Same return types**: `str` for normal, `AsyncIterator[str]` for streaming.
- **Same side effects**: Memory storage, mood updates, correlation IDs behave identically.
- **Same error behavior**: `RuntimeError` for missing LLM client, planning errors handled same way.
- **Existing tests pass**: All current tests should pass without modification after integration.

---

## 5. File Structure

```
src/persona_agent/core/pipeline/
├── __init__.py              # Exports: ChatPipeline, ChatContext, StageResult, PipelineStage
├── context.py               # ChatContext, StageResult dataclasses
├── stage.py                 # PipelineStage protocol
├── pipeline.py              # ChatPipeline orchestrator
└── stages/
    ├── __init__.py          # Exports all stage classes
    ├── validation.py        # ValidationStage
    ├── skill_execution.py   # SkillExecutionStage
    ├── planning.py          # PlanningExecutionStage
    ├── context_prep.py      # ContextPreparationStage
    ├── generation.py        # ResponseGenerationStage
    ├── memory_store.py      # MemoryStorageStage
    └── cleanup.py           # CleanupStage

tests/unit/core/pipeline/
├── __init__.py
├── test_context.py          # ChatContext, StageResult tests
├── test_pipeline.py         # ChatPipeline orchestrator tests
└── stages/
    ├── __init__.py
    ├── test_validation.py
    ├── test_skill_execution.py
    ├── test_planning.py
    ├── test_context_prep.py
    ├── test_generation.py
    ├── test_memory_store.py
    └── test_cleanup.py
```

**Total new files**: 15 (7 source + 8 test files)
**Modified files**: 1 (`agent_engine.py`)

---

## 6. TDD Implementation Plan

### Phase 1: Write Tests First

For each commit, follow this order:
1. Write failing tests for the new component
2. Implement the component to make tests pass
3. Run existing test suite to check for regressions
4. Commit

### Phase 2: Test Categories

#### Unit Tests per Stage
Each stage gets comprehensive unit tests:

```python
# Example: tests/unit/core/pipeline/stages/test_validation.py
import pytest
from unittest.mock import MagicMock, patch
from persona_agent.core.pipeline.stages.validation import ValidationStage
from persona_agent.core.pipeline.context import ChatContext

class TestValidationStage:
    def test_sets_correlation_id(self):
        llm_client = MagicMock()
        stage = ValidationStage(llm_client)
        context = ChatContext(user_input="hello", session_id="test")
        
        result = stage.process(context)
        
        assert result.context.correlation_id is not None
        assert len(result.context.correlation_id) == 36
    
    def test_allows_continuation(self):
        stage = ValidationStage(MagicMock())
        context = ChatContext(user_input="hello", session_id="test")
        
        result = stage.process(context)
        
        assert result.should_continue is True
    
    def test_raises_without_llm_client(self):
        stage = ValidationStage(None)
        context = ChatContext(user_input="hello", session_id="test")
        
        with pytest.raises(RuntimeError, match="LLM client not configured"):
            stage.process(context)
    
    @patch("persona_agent.core.pipeline.stages.validation.set_correlation_id")
    def test_sets_correlation_id_in_logging(self, mock_set):
        stage = ValidationStage(MagicMock())
        context = ChatContext(user_input="hello", session_id="test")
        
        stage.process(context)
        
        mock_set.assert_called_once()
```

#### Pipeline Orchestrator Tests
```python
# tests/unit/core/pipeline/test_pipeline.py
class TestChatPipeline:
    @pytest.mark.asyncio
    async def test_executes_stages_in_order(self):
        calls = []
        
        class TrackingStage:
            def __init__(self, name):
                self.name = name
            async def process(self, ctx):
                calls.append(self.name)
                return StageResult(ctx)
        
        pipeline = ChatPipeline([
            TrackingStage("a"),
            TrackingStage("b"),
            TrackingStage("c"),
        ])
        
        await pipeline.execute(ChatContext(user_input="hi", session_id="test"))
        
        assert calls == ["a", "b", "c"]
    
    @pytest.mark.asyncio
    async def test_short_circuits_on_false(self):
        class StopStage:
            async def process(self, ctx):
                return StageResult(ctx, should_continue=False)
        
        class ShouldNotRun:
            async def process(self, ctx):
                raise AssertionError("Should not run")
        
        pipeline = ChatPipeline([
            StopStage(),
            ShouldNotRun(),
        ])
        
        result = await pipeline.execute(ChatContext(user_input="hi", session_id="test"))
        assert result is not None  # No exception
    
    @pytest.mark.asyncio
    async def test_cleanup_runs_in_finally(self):
        cleanup_calls = []
        
        class FailingStage:
            async def process(self, ctx):
                raise ValueError("boom")
        
        class CleanupStage:
            async def process(self, ctx):
                cleanup_calls.append(True)
                return StageResult(ctx)
        
        pipeline = ChatPipeline(
            stages=[FailingStage()],
            cleanup_stage=CleanupStage(),
        )
        
        with pytest.raises(ValueError):
            await pipeline.execute(ChatContext(user_input="hi", session_id="test"))
        
        assert cleanup_calls == [True]
    
    @pytest.mark.asyncio
    async def test_cleanup_errors_dont_mask_original(self):
        class FailingStage:
            async def process(self, ctx):
                raise ValueError("original error")
        
        class FailingCleanup:
            async def process(self, ctx):
                raise RuntimeError("cleanup error")
        
        pipeline = ChatPipeline(
            stages=[FailingStage()],
            cleanup_stage=FailingCleanup(),
        )
        
        with pytest.raises(ValueError, match="original error"):
            await pipeline.execute(ChatContext(user_input="hi", session_id="test"))
```

#### Integration Tests
```python
# tests/unit/core/test_agent_engine.py (updated)
class TestAgentEnginePipeline:
    @pytest.mark.asyncio
    async def test_chat_uses_configured_pipeline(self):
        """AgentEngine delegates to injected pipeline."""
        mock_pipeline = AsyncMock()
        mock_context = ChatContext(
            user_input="hello",
            session_id="test",
            response="Mocked response",
        )
        mock_pipeline.execute.return_value = mock_context
        
        engine = AgentEngine(
            llm_client=MagicMock(),
            pipeline=mock_pipeline,
        )
        
        result = await engine.chat("hello")
        
        assert result == "Mocked response"
        mock_pipeline.execute.assert_called_once()
        # Verify context was properly initialized
        call_args = mock_pipeline.execute.call_args[0][0]
        assert call_args.user_input == "hello"
        assert call_args.session_id == engine.session_id
```

#### Regression Tests
All existing tests in `tests/unit/core/test_agent_engine.py` must pass without modification after the refactoring. This is verified after each commit.

---

## 7. Atomic Commit Strategy

### Commit 1: Pipeline Core Abstractions
**Scope**: Infrastructure - no behavior change to AgentEngine
- Add `ChatContext`, `StageResult` dataclasses
- Add `PipelineStage` protocol
- Add `ChatPipeline` orchestrator with tests
- **Tests**: `test_context.py`, `test_pipeline.py`
- **Risk**: Very Low (new files only)
- **Verification**: `pytest tests/unit/core/pipeline/ -v`

### Commit 2: Validation + Cleanup Stages
**Scope**: Extract simplest stages first
- Add `ValidationStage` with tests
- Add `CleanupStage` with tests
- **Tests**: `test_validation.py`, `test_cleanup.py`
- **Risk**: Very Low (new files only)

### Commit 3: Skill Execution Stage
**Scope**: Extract skill matching logic
- Add `SkillExecutionStage` with tests
- **Tests**: `test_skill_execution.py`
- **Risk**: Low (new file, well-isolated logic)

### Commit 4: Planning Execution Stage
**Scope**: Extract planning flow
- Add `PlanningExecutionStage` with tests
- Move `_format_plan_results()` logic into stage
- **Tests**: `test_planning.py`
- **Risk**: Low-Medium (complex logic, but isolated)

### Commit 5: Context Preparation Stage
**Scope**: Extract context building
- Add `ContextPreparationStage` with tests
- **Tests**: `test_context_prep.py`
- **Risk**: Low

### Commit 6: Generation + Memory Storage Stages
**Scope**: Extract LLM interaction and persistence
- Add `ResponseGenerationStage` with tests (both streaming and normal)
- Add `MemoryStorageStage` with tests
- **Tests**: `test_generation.py`, `test_memory_store.py`
- **Risk**: Medium (streaming async iterator wrapper needs careful testing)

### Commit 7: AgentEngine Integration
**Scope**: Wire pipeline into AgentEngine
- Refactor `AgentEngine` to use `ChatPipeline`
- Remove extracted private methods (`_handle_with_planning`, `_stream_response`, `_apply_style`, `_store_exchange`, `_format_plan_results`)
- Update existing tests if needed (should be minimal)
- **Risk**: Medium (modifies existing production code)
- **Verification**: All existing tests pass + new integration tests

### Commit 8: DI Container Registration (Optional)
**Scope**: Register stages in DI container
- Add pipeline factory to container bootstrap
- Add integration test for DI wiring
- **Risk**: Low

---

## 8. Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| **Breaking backward compatibility** | Keep exact `chat()` signature. Run full existing test suite after each commit. Add integration tests comparing old vs new behavior. |
| **Streaming bugs** | Create comprehensive tests for async iterator wrapper. Test partial consumption, full consumption, and exception during stream. |
| **Planning path regression** | Extract `_handle_with_planning()` as-is first, then refactor. Preserve existing behavior (no style application, no memory storage for planning). |
| **Memory/performance overhead** | Pipeline adds one object allocation per chat (ChatContext). Negligible impact. No additional I/O. |
| **Test flakiness** | All stage tests use mocked dependencies (no real LLM calls). Use container `override()` for deterministic DI in tests. |
| **Merge conflicts** | Small, focused commits. Each commit is independently reviewable. Coordinate if others are modifying AgentEngine. |

---

## 9. Future Enhancements (Post-MVP)

After the pipeline is stable, these improvements become trivial:

1. **Stage reordering**: Change stage order via configuration without code changes
2. **Conditional stages**: Add predicate-based stage execution (e.g., skip memory for certain personas)
3. **Stage middleware**: Add cross-cutting concerns (timing, logging, retries) via interceptor stages
4. **Parallel stage execution**: Use DAG pattern for independent stages (e.g., mood update + memory retrieval in parallel)
5. **Custom pipelines**: Users can inject their own pipeline configuration for specialized behaviors
6. **Planning normalization**: Make planning path store memories and apply style (currently inconsistent with normal flow)

---

## 10. Open Questions

Before implementation begins, please confirm:

1. **Planning path behavior**: Currently planning responses bypass mood update, style application, and normal memory storage. Should we preserve this inconsistency, or normalize planning to use the full pipeline?

2. **Stage granularity**: Are 7 stages the right level of granularity? We could merge some (e.g., Validation + Cleanup as "InfrastructureStages") or split others (e.g., ContextPreparation into MoodUpdate + MemoryLoad + MessageBuild).

3. **Configuration**: Should the pipeline support YAML/JSON configuration (e.g., disable certain stages per-deployment), or is programmatic configuration via DI sufficient for now?

---

## Appendix: Quick Reference

**Lines to extract from AgentEngine:**
- `chat()` lines 103-158 -> orchestrated by ChatPipeline
- `_handle_with_planning()` lines 160-199 -> PlanningExecutionStage
- `_format_plan_results()` lines 201-230 -> PlanningExecutionStage._format_results()
- `_stream_response()` lines 232-253 -> ResponseGenerationStage._create_streaming_response()
- `_apply_style()` lines 255-268 -> ResponseGenerationStage._apply_style()
- `_store_exchange()` lines 270-281 -> MemoryStorageStage

**Expected final AgentEngine size**: ~150 lines (down from 367)

**New test coverage target**: 100% of pipeline stages, 100% of orchestrator branches
