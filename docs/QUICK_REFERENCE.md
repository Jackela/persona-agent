# Persona-Agent Optimization - Quick Reference

## Research Summary

### Projects Analyzed
| Project | Stars | Key Innovation |
|---------|-------|----------------|
| **AutoGPT** | 182k | Autonomous task planning & execution |
| **Dify** | 136k | Visual workflow builder, RAG pipeline |
| **CrewAI** | 44k | Role-based multi-agent teams, 4-tier memory |
| **LangGraph** | 25k | Stateful workflow graphs with cycles |
| **OpenAI Agents SDK** | 19k | Minimalist, tracer-native design |
| **OpenSpace** | N/A | Self-evolving skills (3 modes) |
| **OpenClaw** | N/A | Local-first Markdown memory, heartbeat |

### What Persona-Agent Already Has (Strengths)
- Hierarchical memory (Working + Episodic + Semantic) - matches CrewAI's approach
- Skill registry with lazy loading - solid foundation
- MCP client for tool integration - forward-looking
- Mood engine + linguistic style - differentiation
- Clean Service Layer architecture - maintainable

### Key Gaps Identified
1. No planning system for multi-step tasks
2. Static skills (no self-evolution)
3. Memory grows indefinitely (no compaction)
4. Single agent only (no multi-agent)
5. No workflow/state machine support

---

## Recommended Implementation Order

### This Week (Quick Wins)

#### 1. Planning System Foundation (~2-3 days)
**Why first:** High impact, builds on existing architecture, enables complex tasks

```bash
# Files to create
src/persona_agent/core/planning/
├── __init__.py
├── models.py      # Task, Plan dataclasses
├── engine.py      # PlanningEngine (LLM-based decomposition)
└── executor.py    # PlanExecutor (state management)

# Files to modify
src/persona_agent/core/agent_engine.py  # Integrate planning
src/persona_agent/ui/cli.py             # Add /plan commands
```

**Key behaviors:**
- Auto-detect when planning is needed (keyword + LLM classification)
- Decompose goals into task DAG
- Execute with dependency resolution
- Handle failures with retry/refinement

#### 2. Skill Evolution Tracker (~1-2 days)
**Why second:** Differentiating feature from OpenSpace research

```bash
# Files to create
src/persona_agent/skills/evolution.py   # Evolution tracking
src/persona_agent/skills/metrics.py     # Metrics aggregation

# Files to modify
src/persona_agent/skills/registry.py    # Record executions
```

**Key behaviors:**
- Track skill success rates
- Detect when skills need improvement (< 70% success)
- Generate FIX/DERIVED variants using LLM
- Require human approval before activation

#### 3. Memory Compaction (~1 day)
**Why third:** Prevents unbounded growth, improves performance

```bash
# Files to create
src/persona_agent/core/memory_compaction.py

# Files to modify
src/persona_agent/core/hierarchical_memory.py  # Add compaction hook
```

**Key behaviors:**
- Daily background compaction
- Group old memories by time window
- Generate LLM summaries
- Mark originals as compacted

---

## Decision Matrix: What to Build Next

```
                    High Impact
                         │
    ┌────────────────────┼────────────────────┐
    │                    │                    │
    │  Planning System   │   Multi-Agent      │
    │  (DO THIS NOW)     │   (LATER)          │
    │                    │                    │
Low Effort ──────────────┼──────────────────── High Effort
    │                    │                    │
    │  Memory Compaction │   Workflow Graph   │
    │  (QUICK WIN)       │   (MEDIUM TERM)    │
    │                    │                    │
    └────────────────────┼────────────────────┘
                         │
                    Low Impact
```

---

## Code Patterns to Follow

### Pattern 1: Async Service Methods
```python
# Current pattern (correct)
class ChatService:
    async def create_session(self, ...) -> ChatSession:
        async with self as service:
            # ... implementation
            return session
```

### Pattern 2: Repository Pattern
```python
# Current pattern (correct)
class SessionRepository(BaseRepository[SessionModel]):
    async def create(self, data: dict) -> SessionModel:
        # ... implementation with error handling
```

### Pattern 3: Skill Registration
```python
# Current pattern (correct)
class MySkill(BaseSkill):
    name = "my_skill"
    description = "Does something"

    async def can_handle(self, context: SkillContext) -> bool:
        return "trigger" in context.user_input.lower()

    async def execute(self, context: SkillContext) -> SkillResult:
        return SkillResult(success=True, response="Done")
```

---

## Testing Checklist

Before implementing each feature:

- [ ] Unit tests for new models/dataclasses
- [ ] Integration tests with mocked LLM calls
- [ ] CLI command tests using CliRunner
- [ ] Memory/performance benchmarks (if applicable)

---

## Configuration Template

Add to `config.yaml`:

```yaml
# New: Planning configuration
planning:
  enabled: true
  auto_detect: true              # Auto-detect when planning is needed
  max_concurrent_tasks: 3        # Limit parallel task execution
  default_max_retries: 1         # Per-task retry count

# New: Skill evolution
evolution:
  enabled: true
  min_executions: 5              # Before considering evolution
  success_threshold: 0.7         # Below this triggers FIX mode
  auto_propose: false            # Require human approval
  storage_path: "./data/skills/evolved"

# New: Memory compaction
memory:
  compaction:
    enabled: true
    older_than_days: 7
    min_group_size: 5
    check_interval_hours: 24
    max_summary_length: 500
```

---

## Common Pitfalls to Avoid

1. **Don't block the event loop**
   - Always use `await` for I/O
   - Use `asyncio.gather()` for parallel tasks

2. **Don't leak memory**
   - Use weakrefs for circular references
   - Clean up old plan executors

3. **Don't ignore LLM failures**
   - Always have fallbacks for parsing
   - Validate structured outputs

4. **Don't break existing CLI**
   - Maintain backward compatibility
   - Add new commands as subcommands

---

## Success Metrics

Track these to measure improvement:

| Metric | Baseline | Target |
|--------|----------|--------|
| Test coverage | ~85% | > 90% |
| Plan completion rate | N/A | > 70% |
| Skill success rate | Unknown | > 80% |
| Memory query latency | ~50ms | < 100ms @ 10k entries |
| Avg response time | ~2s | < 3s with planning |
