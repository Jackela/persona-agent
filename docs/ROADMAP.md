# Persona-Agent Improvement Roadmap

## Executive Summary

Based on comprehensive research of agentic AI projects (AutoGPT, CrewAI, LangGraph, OpenSpace, OpenClaw), this roadmap prioritizes improvements that leverage persona-agent's existing strengths while addressing critical gaps.

**Current Strengths:**
- Mature hierarchical memory system (Working + Episodic + Semantic)
- Well-designed skill registry with lazy loading
- MCP tool integration foundation
- Clean Service Layer architecture
- Mood engine and linguistic style customization

---

## Phase 1: Quick Wins (This Week)

### 1.1 Planning System Foundation ⭐ HIGH PRIORITY
**Reference:** AutoGPT task planning, OpenAI Agents SDK

**Problem:** Current agent engine processes each message independently without multi-step planning.

**Implementation:**
```python
# src/persona_agent/core/planning.py
@dataclass
class Task:
    id: str
    description: str
    status: "pending" | "in_progress" | "completed" | "failed"
    dependencies: list[str]
    result: Any = None

class Plan:
    def __init__(self, goal: str):
        self.goal = goal
        self.tasks: list[Task] = []
        self.current_task_index = 0

class PlanningEngine:
    async def create_plan(self, goal: str, context: dict) -> Plan:
        """Generate task decomposition using LLM."""
        # Use structured output to get task list
        pass

    async def execute_plan(self, plan: Plan, agent_engine: AgentEngine) -> dict:
        """Execute tasks with dependency resolution."""
        pass
```

**Files to modify:**
- Create: `src/persona_agent/core/planning.py`
- Update: `src/persona_agent/core/agent_engine.py` - integrate plan execution
- Update: `src/persona_agent/ui/cli.py` - add `/plan` command

---

### 1.2 Skill Self-Evolution System ⭐ HIGH PRIORITY
**Reference:** OpenSpace FIX/DERIVED/CAPTURED modes

**Problem:** Skills are static; no learning from successful executions.

**Implementation:**
```python
# src/persona_agent/skills/evolution.py
class SkillEvolutionMode(Enum):
    FIX = "fix"           # Fix bugs in existing skills
    DERIVED = "derived"   # Create variants from successful patterns
    CAPTURED = "captured" # Capture new skills from conversations

class SkillEvolutionTracker:
    """Track skill performance and trigger evolution."""

    def record_execution(self, skill_name: str, context: SkillContext, result: SkillResult):
        # Track success rate, execution time, user satisfaction
        pass

    async def evolve_skill(self, skill_name: str, mode: SkillEvolutionMode):
        # Use LLM to generate improved skill code
        pass
```

**Storage:** Add `skill_evolution` table to SQLite schema.

---

### 1.3 Memory Compaction & Summarization
**Reference:** CrewAI 4-tier memory, LangGraph checkpointing

**Problem:** Episodic memory grows indefinitely; no automatic summarization.

**Implementation:**
```python
# Add to src/persona_agent/core/hierarchical_memory.py

class MemoryCompactor:
    """Compact old episodic memories into summaries."""

    async def compact_old_memories(
        self,
        older_than_days: int = 7,
        min_memories: int = 5
    ) -> list[MemoryEntry]:
        # Group memories by time window
        # Generate summary using LLM
        # Store summary as new episodic memory with higher importance
        # Mark original memories as compacted
        pass
```

**Trigger:** Run compaction as background task every N messages.

---

## Phase 2: Medium-Term Enhancements (2-4 Weeks)

### 2.1 Workflow/Graph System
**Reference:** LangGraph state machines, n8n workflows

**Problem:** No way to define multi-step conversational workflows.

**Implementation:**
```python
# src/persona_agent/workflows/graph.py

@dataclass
class WorkflowNode:
    id: str
    node_type: "llm" | "skill" | "mcp" | "condition" | "join"
    config: dict
    transitions: dict[str, str]  # condition -> next_node_id

class WorkflowGraph:
    """Directed graph for workflow execution."""

    def __init__(self):
        self.nodes: dict[str, WorkflowNode] = {}
        self.start_node: str | None = None

    async def execute(
        self,
        input_data: dict,
        context: WorkflowContext
    ) -> WorkflowResult:
        # Traverse graph, execute nodes, maintain state
        pass
```

**Use cases:**
- Onboarding flow for new users
- Multi-turn information gathering
- Structured interview/conversation patterns

---

### 2.2 Multi-Agent Orchestration
**Reference:** CrewAI role-based teams, AutoGen conversational agents

**Problem:** Single agent only; no multi-agent collaboration.

**Implementation:**
```python
# src/persona_agent/orchestration/multi_agent.py

@dataclass
class AgentRole:
    name: str
    persona: str  # Character name
    skills: list[str]
    can_delegate_to: list[str]
    system_prompt_addition: str

class AgentTeam:
    """Team of specialized agents working together."""

    def __init__(self, roles: list[AgentRole]):
        self.agents: dict[str, AgentEngine] = {}
        self.message_bus: asyncio.Queue = asyncio.Queue()

    async def broadcast(self, message: AgentMessage):
        # Send message to all agents
        pass

    async def delegate(self, from_agent: str, to_agent: str, task: str):
        # One agent delegates task to another
        pass
```

---

### 2.3 Dependency Injection Container
**Reference:** Modern Python DI patterns (dependency-injector, injector)

**Problem:** Services are instantiated directly; tight coupling.

**Implementation:**
```python
# src/persona_agent/di/container.py

class DIContainer:
    """Simple DI container for service management."""

    def __init__(self):
        self._registrations: dict[type, Callable] = {}
        self._singletons: dict[type, Any] = {}

    def register_singleton[T](self, interface: type[T], implementation: Callable[[], T]):
        self._registrations[interface] = implementation

    def resolve[T](self, interface: type[T]) -> T:
        if interface not in self._singletons:
            factory = self._registrations.get(interface)
            if factory:
                self._singletons[interface] = factory()
        return self._singletons[interface]

# Usage in services
container = DIContainer()
container.register_singleton(SessionRepository, lambda: SessionRepository(db_path))
container.register_singleton(CharacterService, lambda: CharacterService(
    character_repo=container.resolve(CharacterRepository),
    validator=container.resolve(ConfigValidator)
))
```

**Benefits:**
- Easier testing (mock injection)
- Lifecycle management
- Configuration-driven instantiation

---

### 2.4 Human-in-the-Loop Mode
**Reference:** LangGraph interrupts, OpenClaw heartbeat

**Problem:** No way to pause execution for human approval/feedback.

**Implementation:**
```python
# src/persona_agent/core/human_in_loop.py

class HumanInterrupt:
    """Pause execution and wait for human input."""

    async def request_approval(
        self,
        action_description: str,
        proposed_action: dict
    ) -> ApprovalResult:
        # Send notification (CLI prompt, webhook, etc.)
        # Wait for human response
        pass

class HeartbeatMonitor:
    """Monitor agent health and trigger interventions."""

    async def heartbeat(self):
        # Track last activity
        # Alert if stuck or looping
        pass
```

---

## Phase 3: Long-Term Architecture (1-3 Months)

### 3.1 Advanced Memory: Vector Graph Hybrid
**Reference:** Mem0, GraphRAG

**Idea:** Combine vector similarity with graph traversal for richer retrieval.

```
Current: Vector similarity search
Future:  Vector search + Graph traversal + Relationship weighting
```

**Implementation:**
- Extend `SemanticMemory` with vector embeddings for entities
- Add relationship strength based on co-occurrence frequency
- Implement multi-hop reasoning: "Find friends of friends who like X"

---

### 3.2 Plugin Marketplace Foundation
**Reference:** Obsidian plugins, VSCode extensions

**Idea:** Third-party skill and persona marketplace.

**Components:**
- Plugin manifest format (JSON schema)
- Sandboxed skill execution
- Version management
- Plugin API for extending core functionality

---

### 3.3 Distributed Agent Swarm
**Reference:** AutoGPT multi-agent, MetaGPT

**Idea:** Agents running on different machines collaborating.

**Components:**
- Message broker (Redis/RabbitMQ)
- Agent discovery protocol
- Consensus mechanisms for shared state
- Fault tolerance and leader election

---

## Implementation Priority Matrix

| Feature | Impact | Effort | Priority |
|---------|--------|--------|----------|
| Planning System | High | Medium | P1 |
| Skill Evolution | High | Medium | P1 |
| Memory Compaction | Medium | Low | P1 |
| Workflow Graph | High | High | P2 |
| Multi-Agent | High | High | P2 |
| DI Container | Medium | Low | P2 |
| Human-in-Loop | High | Medium | P2 |
| Vector Graph Hybrid | Medium | High | P3 |
| Plugin Marketplace | High | Very High | P3 |
| Distributed Swarm | Very High | Very High | P3 |

---

## Technical Debt & Code Quality

### Immediate
- [ ] Complete test coverage for `hierarchical_memory.py` (currently ~60%)
- [ ] Add integration tests for MCP tool execution
- [ ] Document skill development guide

### Short-term
- [ ] Migrate to Pydantic v2 models across codebase
- [ ] Add OpenTelemetry instrumentation
- [ ] Implement proper async connection pooling for repositories

### Long-term
- [ ] Consider Rust extensions for hot paths (embedding, vector ops)
- [ ] Evaluate migration to SQLAlchemy 2.0 for ORM

---

## Metrics & Success Criteria

### Planning System
- Successfully decomposes 80%+ of complex user requests into actionable tasks
- Average plan completion rate > 70%

### Skill Evolution
- 20%+ reduction in repeated skill failures over 100 executions
- Zero manual intervention for bug fixes in derived skills

### Memory System
- Query latency < 100ms for 10k memories
- 50%+ reduction in redundant context window usage

### Multi-Agent
- Successfully coordinate 3+ agents for complex tasks
- Message overhead < 20% of total processing time

---

## Appendix: Research Sources

### Projects Analyzed
1. **AutoGPT** (182k ⭐) - Task planning, autonomous execution
2. **CrewAI** (44.3k ⭐) - Role-based teams, 4-tier memory
3. **LangGraph** (24.8k ⭐) - Stateful workflow graphs
4. **OpenAI Agents SDK** (19k ⭐) - Minimalist design patterns
5. **OpenSpace** - Self-evolving skills (FIX/DERIVED/CAPTURED)
6. **OpenClaw** - Local-first memory, heartbeat monitoring

### Key Insights
- Planning systems are becoming table stakes (AutoGPT, OpenAI Agents SDK)
- Memory systems are converging on hierarchical designs (CrewAI, our current impl)
- Multi-agent requires careful orchestration (CrewAI's role-based approach is proven)
- Tool ecosystems benefit from standardization (MCP is the right bet)
