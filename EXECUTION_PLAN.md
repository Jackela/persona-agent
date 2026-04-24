# Persona-Agent Comprehensive Improvement Plan

## Executive Summary

This plan delivers a systematic 3-phase improvement of the persona-agent Python AI Agent Framework. All work is designed for parallel execution by subagents with clear verification checkpoints and atomic commits.

**Current State Baseline:**
- Tests: ~871 collected, unknown passing (1 known failure in test_end_to_end.py)
- MyPy: 48 errors in 13 files
- Ruff: 0 issues (clean)
- Bandit: 20 issues (3 medium, 17 low)
- Coverage gaps: memory_store_v2 (0%), cognitive_emotional_engine (low), consistency_validator (low), user_modeling (low), skills (low)

---

## Phase 1: Foundation (Infrastructure + Exceptions + Type Safety)

### Phase 1 Goal
Establish a clean foundation by fixing infrastructure issues, unifying exceptions, and resolving all mypy errors while maintaining test compatibility.

### Phase 1A: Infrastructure Improvements (Parallel Batch)

#### Task 1.1: Add LLM Retry Logic
- **File**: `src/persona_agent/utils/llm_client.py` (402 lines)
- **What**: Add tenacity retry decorators to LLM client methods (`chat`, `chat_stream`, `embed`)
- **Dependencies**: None
- **Estimated Effort**: Small (30-60 min)
- **Success Criteria**:
  - Retry with exponential backoff on `APIRateLimitError`, `TimeoutError`, connection errors
  - Max 3 retries, configurable via settings
  - All existing tests pass
  - New test: `tests/unit/utils/test_llm_client.py` - verify retry behavior with mocked failures
- **Atomic Commit**: `feat(infra): add tenacity retry logic to LLM client`

#### Task 1.2: Simplify Pydantic Validators
- **File**: `src/persona_agent/config/schemas/settings.py` (355 lines)
- **What**: Simplify complex validators, fix missing type annotation for `result` variable
- **Dependencies**: None
- **Estimated Effort**: Small (30-45 min)
- **Success Criteria**:
  - Fix mypy error at line 320: `Need type annotation for "result"`
  - Simplify any overly complex validators while preserving behavior
  - All settings tests pass
- **Atomic Commit**: `refactor(config): simplify pydantic validators and fix type annotations`

#### Task 1.3: Add Correlation IDs to Logging
- **File**: `src/persona_agent/utils/logging_config.py` (141 lines)
- **What**: Add correlation ID filter and formatter support
- **Dependencies**: None
- **Estimated Effort**: Small (30-45 min)
- **Success Criteria**:
  - Generate or accept correlation ID per request/session
  - Include in all log output (JSON and console formats)
  - Test: `tests/unit/utils/test_logging.py` - verify correlation ID appears in logs
- **Atomic Commit**: `feat(logging): add correlation ID support`

#### Task 1.4: Delete Dead Code
- **Files**: 
  - `src/persona_agent/core/agent_engine_refactored.py` (590 lines)
  - `src/persona_agent/core/persona_manager_refactored.py` (470 lines)
- **What**: Delete both files (confirmed: zero imports across codebase)
- **Dependencies**: None
- **Estimated Effort**: Tiny (5 min)
- **Success Criteria**:
  - Files removed
  - No import errors
  - All tests pass
- **Atomic Commit**: `chore(cleanup): remove dead code files agent_engine_refactored and persona_manager_refactored`

### Phase 1B: Exception Unification (Sequential - After 1A)

#### Task 1.5: Create Unified Exception Hierarchy
- **File**: `src/persona_agent/exceptions.py` (new unified file) or update `src/persona_agent/utils/exceptions.py`
- **What**: 
  - Make `PlanningError`, `MemoryError`, `EvolutionError` inherit from `PersonaAgentError`
  - Fix shadowing: `consistency_validator.ValidationError` -> use `utils.exceptions.ValidationError`
  - Fix duplication: consolidate duplicate `InvalidPlanStateError`
  - Fix built-in shadowing: rename `FileNotFoundError` and `TimeoutError` to avoid shadowing Python builtins
- **Dependencies**: Task 1.4 complete (dead code removed)
- **Estimated Effort**: Medium (1-2 hours)
- **Success Criteria**:
  - All subsystem exceptions inherit from `PersonaAgentError`
  - No more shadowing of built-in exceptions
  - All raise/except sites updated
  - Tests: `tests/test_exceptions.py` - verify hierarchy and inheritance
- **Files to Update**:
  - `src/persona_agent/utils/exceptions.py` (add PlanningError, MemoryError, ToolError bases)
  - `src/persona_agent/core/planning/exceptions.py` (change base to PersonaAgentError)
  - `src/persona_agent/core/memory/exceptions.py` (change base to PersonaAgentError)
  - `src/persona_agent/skills/evolution/exceptions.py` (change base to PersonaAgentError)
  - `src/persona_agent/core/consistency_validator.py` (remove local ValidationError)
  - `src/persona_agent/core/planning/models.py` (remove duplicate InvalidPlanStateError)
  - `src/persona_agent/tools/sandbox.py` (rename SecurityError, TimeoutError, MemoryLimitError if needed)
- **Atomic Commit**: `refactor(exceptions): unify exception hierarchy under PersonaAgentError`

### Phase 1C: Fix MyPy Errors (Parallel Batch - After 1A)

#### Task 1.6: Fix Memory Store None Handling
- **Files**: 
  - `src/persona_agent/core/memory_store.py` (9 errors)
  - `src/persona_agent/core/memory_store_v2.py` (11 errors)
- **What**: 
  - Add null checks before passing to `json.loads`
  - Handle `str | None` for `user_message` and `assistant_message`
  - Fix `Row` attribute access (use index access or ensure proper type)
  - Fix incompatible override in `retrieve_relevant`
- **Dependencies**: None (can run parallel with 1.5)
- **Estimated Effort**: Medium (1-2 hours)
- **Success Criteria**:
  - All 20 mypy errors in memory stores resolved
  - No runtime behavior changes
  - All memory tests pass: `pytest tests/unit/core/test_memory_store.py`
- **Atomic Commit**: `fix(types): resolve mypy errors in memory stores`

#### Task 1.7: Fix Planning Executor Collection Types
- **File**: `src/persona_agent/core/planning/executor.py` (3 errors)
- **What**: 
  - Fix `Collection[str]` used as mutable list (change to `list[str]` or `MutableSequence[str]`)
  - Fix `TaskResult.success_result` type for `output` field
- **Dependencies**: None
- **Estimated Effort**: Small (20-30 min)
- **Success Criteria**:
  - All 3 executor mypy errors resolved
  - Planning tests pass: `pytest tests/unit/core/planning/`
- **Atomic Commit**: `fix(types): correct Collection type usage in planning executor`

#### Task 1.8: Fix Remaining MyPy Errors
- **Files**:
  - `src/persona_agent/utils/llm_client.py` (1 error - AsyncClient base_url)
  - `src/persona_agent/core/importance_scorer.py` (1 error - LLMClient | None)
  - `src/persona_agent/core/memory_compression.py` (2 errors)
  - `src/persona_agent/tools/base.py` (1 error)
  - `src/persona_agent/tools/discovery.py` (2 errors)
  - `src/persona_agent/config/schemas/settings.py` (1 error - already fixed in 1.2)
  - `src/persona_agent/core/planning/engine.py` (1 error)
  - `src/persona_agent/core/memory/summarizer.py` (2 errors)
  - `src/persona_agent/ui/web/server.py` (1 error)
  - `src/persona_agent/core/vector_memory.py` (5 errors)
- **What**: Fix all remaining mypy errors
- **Dependencies**: None
- **Estimated Effort**: Medium (1-2 hours)
- **Success Criteria**:
  - `mypy src` shows 0 errors
  - All related tests pass
- **Atomic Commit**: `fix(types): resolve remaining mypy errors across codebase`

### Phase 1 Verification Checkpoint
```bash
# Run these commands to verify Phase 1 completion:
mypy src                                          # Must show 0 errors
ruff check src tests                              # Must show 0 issues
pytest tests/unit/utils/test_llm_client.py        # Must pass
pytest tests/unit/core/planning/                  # Must pass
pytest tests/unit/core/test_memory_store.py       # Must pass
pytest tests/test_exceptions.py                   # Must pass
pytest tests/unit/utils/test_logging.py           # Must pass
pytest tests/unit/config/                         # Must pass
bandit -r src                                     # Review any new issues
```

---

## Phase 2: Safety Net (Comprehensive Testing)

### Phase 2 Goal
Achieve comprehensive test coverage for critical untested components while fixing existing test failures.

### Phase 2A: Fix Existing Test Failures (First)

#### Task 2.1: Fix End-to-End Test Failure
- **File**: `tests/integration/test_end_to_end.py`
- **What**: Fix `test_simple_chat_without_planning` - `RuntimeError: No character loaded`
- **Root Cause**: Test creates `AgentEngine` without loading a character
- **Dependencies**: None
- **Estimated Effort**: Small (15-30 min)
- **Success Criteria**:
  - Test loads a character or uses a mock
  - All integration tests pass
- **Atomic Commit**: `fix(tests): load character in end-to-end test`

### Phase 2B: Add Unit Tests (Parallel Batch - After 2.1)

#### Task 2.2: Tests for memory_store_v2.py
- **File**: `src/persona_agent/core/memory_store_v2.py` (568 lines, 0% coverage)
- **New Test File**: `tests/unit/core/test_memory_store_v2.py`
- **What**: Comprehensive unit tests for all public methods
- **Dependencies**: Task 1.6 complete (mypy fixes), Task 2.1 complete
- **Estimated Effort**: Large (3-4 hours)
- **Success Criteria**:
  - Cover: `__init__`, `store_interaction`, `retrieve_relevant`, `get_recent_memories`, `delete_memory`, `clear_session`, `compress_memories`
  - Mock SQLite, embedding model, and LLM
  - Test error paths and edge cases (empty results, encryption, None values)
  - Target: 80%+ coverage
- **TDD Approach**: Write tests first, then verify against fixed code from Phase 1
- **Atomic Commit**: `test(memory): add comprehensive tests for memory_store_v2`

#### Task 2.3: Tests for cognitive_emotional_engine.py
- **File**: `src/persona_agent/core/cognitive_emotional_engine.py` (1102 lines, low coverage)
- **New Test File**: `tests/unit/core/test_cognitive_emotional_engine.py`
- **What**: Unit tests for cognitive-emotional processing
- **Dependencies**: Task 2.1 complete
- **Estimated Effort**: Large (3-4 hours)
- **Success Criteria**:
  - Cover: `process_input`, emotional state updates, VAD model, fusion layer
  - Mock LLM for emotional analysis
  - Test rule-based fallbacks when LLM is None
  - Target: 70%+ coverage
- **Atomic Commit**: `test(core): add tests for cognitive emotional engine`

#### Task 2.4: Tests for consistency_validator.py
- **File**: `src/persona_agent/core/consistency_validator.py` (1022 lines, low coverage)
- **New Test File**: `tests/unit/core/test_consistency_validator.py`
- **What**: Unit tests for validation logic
- **Dependencies**: Task 2.1 complete
- **Estimated Effort**: Large (3-4 hours)
- **Success Criteria**:
  - Cover: validation scoring, self-critique, constitutional checks
  - Mock LLM for critique generation
  - Test all validation dimensions
  - Target: 70%+ coverage
- **Atomic Commit**: `test(core): add tests for consistency validator`

#### Task 2.5: Tests for user_modeling.py
- **File**: `src/persona_agent/core/user_modeling.py` (1120 lines, ~42% coverage)
- **New Test File**: Expand `tests/unit/core/test_user_modeling.py` or create new
- **What**: Fill coverage gaps in user modeling
- **Dependencies**: Task 2.1 complete
- **Estimated Effort**: Medium (2-3 hours)
- **Success Criteria**:
  - Cover: peer cards, conclusions, preference detection, context building
  - Test edge cases: empty history, missing data, update conflicts
  - Target: 80%+ coverage
- **Atomic Commit**: `test(core): expand tests for user modeling`

#### Task 2.6: Tests for Skill System
- **Files**: 
  - `src/persona_agent/skills/registry.py` (298 lines)
  - `src/persona_agent/skills/base.py` (182 lines)
- **New Test File**: `tests/unit/skills/test_registry.py` and expand `tests/unit/skills/test_base.py`
- **What**: Test skill registry and base class
- **Dependencies**: Task 2.1 complete
- **Estimated Effort**: Medium (2 hours)
- **Success Criteria**:
  - Cover: skill registration, discovery, lazy loading, execution
  - Test error handling: SkillNotFoundError, SkillExecutionError
  - Test base skill: context handling, result formatting
  - Target: 80%+ coverage
- **Atomic Commit**: `test(skills): add tests for skill registry and base class`

### Phase 2 Verification Checkpoint
```bash
# Run these commands to verify Phase 2 completion:
pytest tests/                                     # All tests must pass
pytest --cov=src.persona_agent.core.memory_store_v2 --cov-report=term-missing    # 80%+
pytest --cov=src.persona_agent.core.cognitive_emotional_engine --cov-report=term-missing  # 70%+
pytest --cov=src.persona_agent.core.consistency_validator --cov-report=term-missing      # 70%+
pytest --cov=src.persona_agent.core.user_modeling --cov-report=term-missing              # 80%+
pytest --cov=src.persona_agent.skills.registry --cov=src.persona_agent.skills.base --cov-report=term-missing  # 80%+
pytest --cov=src --cov-report=term-missing        # Overall coverage should improve significantly
mypy src                                          # Must show 0 errors
ruff check src tests                              # Must show 0 issues
bandit -r src                                     # Review issues
```

---

## Phase 3: Architecture Refactoring

### Phase 3 Goal
Refactor architecture to reduce coupling, extract pipelines, add DI container, and improve performance.

### Phase 3A: Architecture Improvements (Parallel Batch)

#### Task 3.1: Extract AgentEngine Pipeline Stages
- **File**: `src/persona_agent/core/agent_engine.py` (12,279 lines - god class)
- **What**: Extract pipeline stages from god class using pipeline pattern
- **Dependencies**: Phase 1 and 2 complete
- **Estimated Effort**: Large (4-6 hours)
- **Success Criteria**:
  - Extract stages: InputProcessing, ContextBuilding, LLMInteraction, ResponseProcessing, MemoryUpdate
  - Each stage is independently testable
  - AgentEngine orchestrates stages via pipeline
  - All existing tests pass without modification
  - No public API breakage
- **Design**:
  ```python
  class PipelineStage(ABC):
      @abstractmethod
      async def execute(self, context: AgentContext) -> AgentContext: ...
  
  class AgentPipeline:
      def __init__(self, stages: list[PipelineStage]): ...
      async def run(self, context: AgentContext) -> AgentContext: ...
  ```
- **Atomic Commit**: `refactor(engine): extract pipeline stages from agent engine`

#### Task 3.2: Add Lightweight DI Container
- **New File**: `src/persona_agent/core/container.py`
- **What**: Simple DI container for wiring dependencies
- **Dependencies**: Task 3.1 (understand current dependencies)
- **Estimated Effort**: Medium (2-3 hours)
- **Success Criteria**:
  - Register: LLMClient, MemoryStore, PersonaManager, PlanningEngine, etc.
  - Support factory functions for lazy initialization
  - Allow override for testing
  - No external dependencies (hand-written, ~100 lines)
- **Atomic Commit**: `feat(di): add lightweight dependency injection container`

#### Task 3.3: Async SQLite Operations
- **Files**: 
  - `src/persona_agent/core/memory_store.py`
  - `src/persona_agent/core/memory_store_v2.py`
  - `src/persona_agent/repositories/session_repository.py`
- **What**: Replace synchronous SQLite with aiosqlite
- **Dependencies**: Phase 2 complete (tests in place)
- **Estimated Effort**: Medium (2-3 hours)
- **Success Criteria**:
  - All database operations are async
  - No blocking I/O in async methods
  - All tests pass with async test patterns
  - Performance improvement measurable
- **Atomic Commit**: `perf(db): migrate sqlite operations to aiosqlite`

#### Task 3.4: Add Performance Metrics/Timing Decorators
- **New File**: `src/persona_agent/utils/metrics.py`
- **What**: Decorators for timing and performance metrics
- **Dependencies**: None
- **Estimated Effort**: Small (1-2 hours)
- **Success Criteria**:
  - `@timed` decorator logs execution time
  - `@counted` decorator tracks call counts
  - Optional: expose metrics via Prometheus-style endpoint
  - Test: `tests/unit/utils/test_metrics.py`
- **Atomic Commit**: `feat(metrics): add performance timing and counting decorators`

### Phase 3 Verification Checkpoint
```bash
# Run these commands to verify Phase 3 completion:
pytest tests/                                     # All tests must pass (751+)
mypy src                                          # Must show 0 errors
ruff check src tests                              # Must show 0 issues
bandit -r src                                     # Security check
pytest --benchmark-only                           # Performance benchmarks if available
pytest --cov=src --cov-report=term-missing        # Coverage maintained or improved
```

---

## Parallel Execution Strategy

### Phase 1 Parallel Groups

```
Group 1A (Parallel - No Dependencies):
├── Task 1.1: LLM Retry Logic
├── Task 1.2: Pydantic Validators
├── Task 1.3: Correlation IDs
└── Task 1.4: Delete Dead Code

Group 1B (Parallel - After 1A):
├── Task 1.5: Exception Unification (depends on 1.4)
├── Task 1.6: Memory Store MyPy Fixes (independent of 1.5)
├── Task 1.7: Planning Executor MyPy Fixes (independent)
└── Task 1.8: Remaining MyPy Fixes (independent)
```

### Phase 2 Parallel Groups

```
Task 2.1: Fix E2E Test (First - Blocking)

Group 2B (Parallel - After 2.1):
├── Task 2.2: memory_store_v2 tests
├── Task 2.3: cognitive_emotional_engine tests
├── Task 2.4: consistency_validator tests
├── Task 2.5: user_modeling tests
└── Task 2.6: skill system tests
```

### Phase 3 Parallel Groups

```
Group 3A (Parallel - After Phase 2):
├── Task 3.1: Extract Pipeline Stages
├── Task 3.2: DI Container
├── Task 3.3: Async SQLite
└── Task 3.4: Performance Metrics
```

---

## Atomic Commit Strategy

### Commit Message Format
```
<type>(<scope>): <description>

<body>

Refs: <task-id>
```

### Phase 1 Commits
1. `feat(infra): add tenacity retry logic to LLM client`
2. `refactor(config): simplify pydantic validators and fix type annotations`
3. `feat(logging): add correlation ID support`
4. `chore(cleanup): remove dead code files agent_engine_refactored and persona_manager_refactored`
5. `refactor(exceptions): unify exception hierarchy under PersonaAgentError`
6. `fix(types): resolve mypy errors in memory stores`
7. `fix(types): correct Collection type usage in planning executor`
8. `fix(types): resolve remaining mypy errors across codebase`

### Phase 2 Commits
9. `fix(tests): load character in end-to-end test`
10. `test(memory): add comprehensive tests for memory_store_v2`
11. `test(core): add tests for cognitive emotional engine`
12. `test(core): add tests for consistency validator`
13. `test(core): expand tests for user modeling`
14. `test(skills): add tests for skill registry and base class`

### Phase 3 Commits
15. `refactor(engine): extract pipeline stages from agent engine`
16. `feat(di): add lightweight dependency injection container`
17. `perf(db): migrate sqlite operations to aiosqlite`
18. `feat(metrics): add performance timing and counting decorators`

---

## TDD-Oriented Planning

### Test-First Approach
1. **For each component being fixed/improved**:
   - Write a failing test that demonstrates the issue
   - Fix the implementation
   - Verify test passes
   - Add edge case tests

2. **For new features**:
   - Write test defining expected behavior
   - Implement feature
   - Verify test passes
   - Refactor if needed

3. **Red-Green-Refactor Cycle**:
   - Phase 1: Write tests for mypy fixes (type annotations, null checks)
   - Phase 2: Write tests before implementing new features
   - Phase 3: Write tests for pipeline stages before extraction

### Example TDD Flow for Task 1.6 (MyPy Fix)
```python
# 1. Write test for None handling
def test_memory_store_handles_none_fields():
    store = MemoryStore(":memory:")
    # Should not raise when fields are None
    result = store._deserialize_row({"user_message": None, "assistant_message": None})
    assert result.user_message == ""
    assert result.assistant_message == ""

# 2. Fix implementation to handle None
# 3. Verify test passes
# 4. Add edge case: empty string, missing keys
```

---

## Verification Matrix

| Checkpoint | Command | Phase 1 | Phase 2 | Phase 3 |
|-----------|---------|---------|---------|---------|
| MyPy Clean | `mypy src` | 0 errors | 0 errors | 0 errors |
| Ruff Clean | `ruff check src tests` | 0 issues | 0 issues | 0 issues |
| Tests Pass | `pytest tests/` | All pass | All pass | All pass |
| Coverage | `pytest --cov=src` | Baseline | Improved | Maintained |
| Security | `bandit -r src` | Review | Review | Review |
| Test Count | `pytest --collect-only` | 751+ | 751+ | 751+ |

---

## Risk Mitigation

### Risk: Test breakage during refactoring
- **Mitigation**: Run tests after every commit. Use `-x` flag during development to catch failures early.

### Risk: MyPy fixes change runtime behavior
- **Mitigation**: Add tests before fixing types. Use `cast()` or `assert` only when certain.

### Risk: Exception unification breaks catch blocks
- **Mitigation**: Search all `except` clauses before changing exception hierarchy. Maintain backward compatibility.

### Risk: Pipeline extraction breaks public API
- **Mitigation**: Keep `AgentEngine` class as facade. Extract internal methods only.

---

## Subagent Delegation Instructions

Each task can be delegated to a subagent with the following prompt template:

```
You are implementing Task X.Y for the persona-agent project.

**Context**:
- Project: Python AI Agent Framework at /mnt/d/Code/persona-agent
- Python 3.11+, uses pytest, black, ruff, mypy
- Current branch: main

**Task**: [Description from plan]

**Files**:
- Modify: [list]
- Create: [list]
- Test: [list]

**Constraints**:
- Must not break existing tests
- Must follow existing code style
- Must pass: mypy, ruff, pytest
- Commit with message: "[type]([scope]): [description]"

**Verification**:
After implementation, run:
```bash
mypy src/[relevant_path]
ruff check src tests
pytest tests/[relevant_test_path] -xvs
```

Report results.
```

---

## Estimated Timeline

| Phase | Tasks | Estimated Duration | Parallel Factor |
|-------|-------|-------------------|----------------|
| Phase 1 | 8 tasks | 8-12 hours | 4x parallel = 2-3 hours |
| Phase 2 | 6 tasks | 14-18 hours | 5x parallel = 3-4 hours |
| Phase 3 | 4 tasks | 10-14 hours | 4x parallel = 3-4 hours |
| **Total** | **18 tasks** | **32-44 hours** | **~8-11 hours with parallelism** |

*Note: With 4-5 parallel subagents, the entire plan can execute in approximately 1 working day.*
