"""Unit tests for planning engine components."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from persona_agent.core.planning.engine import (
    IntentClassifier,
    PlanningEngine,
    PlanRefiner,
    TaskDecomposer,
)
from persona_agent.core.planning.exceptions import PlanCreationError
from persona_agent.core.planning.models import (
    Plan,
    PlanningConfig,
    Task,
)
from persona_agent.utils.llm_client import LLMResponse


class TestIntentClassifier:
    """Tests for IntentClassifier."""

    def test_heuristic_simple_greeting(self):
        """Test heuristic correctly identifies simple greetings."""
        classifier = IntentClassifier()

        assert classifier.heuristic_classify("Hello!") is False
        assert classifier.heuristic_classify("Hi there") is False
        assert classifier.heuristic_classify("Good morning") is False

    def test_heuristic_farewell(self):
        """Test heuristic identifies farewells."""
        classifier = IntentClassifier()

        assert classifier.heuristic_classify("Bye") is False
        assert classifier.heuristic_classify("Goodbye") is False

    def test_heuristic_planning_keywords(self):
        """Test heuristic detects planning keywords."""
        classifier = IntentClassifier()

        assert classifier.heuristic_classify("Can you help me plan a trip?") is True
        assert classifier.heuristic_classify("What are the steps to learn Python?") is True
        assert classifier.heuristic_classify("Research the best practices") is True

    def test_heuristic_long_input(self):
        """Test heuristic flags long inputs."""
        classifier = IntentClassifier()

        long_input = "I want you to " + "a" * 200
        assert classifier.heuristic_classify(long_input) is True

    def test_heuristic_uncertain(self):
        """Test heuristic returns None for uncertain inputs."""
        classifier = IntentClassifier()

        # Neutral input
        assert classifier.heuristic_classify("What's the weather?") is None

    @pytest.mark.asyncio
    async def test_llm_classify_true(self):
        """Test LLM classification returns True."""
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = LLMResponse(content="TRUE", model="test")

        classifier = IntentClassifier(mock_llm)
        result = await classifier.llm_classify("Complex task here")

        assert result is True
        mock_llm.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_classify_false(self):
        """Test LLM classification returns False."""
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = LLMResponse(content="FALSE", model="test")

        classifier = IntentClassifier(mock_llm)
        result = await classifier.llm_classify("Simple task")

        assert result is False

    @pytest.mark.asyncio
    async def test_llm_classify_error_fallback(self):
        """Test LLM classification falls back on error."""
        mock_llm = AsyncMock()
        mock_llm.chat.side_effect = Exception("LLM error")

        classifier = IntentClassifier(mock_llm)
        result = await classifier.llm_classify("Task")

        assert result is False  # Default to no planning on error

    @pytest.mark.asyncio
    async def test_classify_uses_heuristic_when_definitive(self):
        """Test classify uses heuristic result when definitive."""
        classifier = IntentClassifier()
        classifier.heuristic_classify = MagicMock(return_value=True)
        classifier.llm_classify = AsyncMock()

        result = await classifier.classify("Plan something")

        assert result is True
        classifier.llm_classify.assert_not_called()

    @pytest.mark.asyncio
    async def test_classify_falls_back_to_llm(self):
        """Test classify falls back to LLM when heuristic uncertain."""
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = LLMResponse(content="TRUE", model="test")

        classifier = IntentClassifier(mock_llm)
        classifier.heuristic_classify = MagicMock(return_value=None)

        result = await classifier.classify("Some input")

        assert result is True


class TestTaskDecomposer:
    """Tests for TaskDecomposer."""

    @pytest.fixture
    def mock_llm(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_decompose_success(self, mock_llm):
        """Test successful task decomposition."""
        response_content = '''{"tasks": [
            {"id": "task_1", "description": "Search for Python docs", "dependencies": []},
            {"id": "task_2", "description": "Read about asyncio", "dependencies": ["task_1"]}
        ], "reasoning": "Need to find docs first"}'''

        mock_llm.chat.return_value = LLMResponse(content=response_content, model="test")

        decomposer = TaskDecomposer(mock_llm)
        tasks = await decomposer.decompose("Learn Python async")

        assert len(tasks) == 2
        assert tasks[0].id == "task_1"
        assert tasks[0].description == "Search for Python docs"
        assert tasks[0].dependencies == []

        assert tasks[1].id == "task_2"
        assert tasks[1].description == "Read about asyncio"
        assert tasks[1].dependencies == ["task_1"]

    @pytest.mark.asyncio
    async def test_decompose_with_context(self, mock_llm):
        """Test decomposition with context."""
        mock_llm.chat.return_value = LLMResponse(
            content='{"tasks": [{"id": "task_1", "description": "Do something", "dependencies": []}]}',
            model="test"
        )

        decomposer = TaskDecomposer(mock_llm)
        context = {"user_level": "beginner", "topic": "Python"}

        await decomposer.decompose("Learn Python", context)

        # Check context was included in prompt
        call_args = mock_llm.chat.call_args
        prompt = call_args[0][0][1]["content"]  # user message content
        assert "beginner" in prompt
        assert "Python" in prompt

    @pytest.mark.asyncio
    async def test_decompose_invalid_json(self, mock_llm):
        """Test handling of invalid JSON response."""
        mock_llm.chat.return_value = LLMResponse(content="Not valid JSON", model="test")

        decomposer = TaskDecomposer(mock_llm)

        with pytest.raises(PlanCreationError):
            await decomposer.decompose("Some goal")

    @pytest.mark.asyncio
    async def test_decompose_missing_tasks_key(self, mock_llm):
        """Test handling of missing tasks key."""
        mock_llm.chat.return_value = LLMResponse(
            content='{"result": "something"}',
            model="test"
        )

        decomposer = TaskDecomposer(mock_llm)

        with pytest.raises(PlanCreationError, match="tasks"):
            await decomposer.decompose("Some goal")

    @pytest.mark.asyncio
    async def test_decompose_llm_error(self, mock_llm):
        """Test handling of LLM error."""
        mock_llm.chat.side_effect = Exception("LLM failed")

        decomposer = TaskDecomposer(mock_llm)

        with pytest.raises(PlanCreationError, match="Failed to decompose"):
            await decomposer.decompose("Some goal")

    @pytest.mark.asyncio
    async def test_decompose_with_markdown_code_block(self, mock_llm):
        """Test extraction from markdown code block."""
        response_content = '''```json
        {"tasks": [{"id": "task_1", "description": "Do it", "dependencies": []}]}
        ```'''

        mock_llm.chat.return_value = LLMResponse(content=response_content, model="test")

        decomposer = TaskDecomposer(mock_llm)
        tasks = await decomposer.decompose("Goal")

        assert len(tasks) == 1

    def test_extract_json_from_markdown(self):
        """Test JSON extraction from markdown."""
        decomposer = TaskDecomposer(AsyncMock())

        # With json tag
        content = "```json\n{\"key\": \"value\"}\n```"
        assert decomposer._extract_json(content) == '{"key": "value"}'

        # Without json tag
        content = "```\n{\"key\": \"value\"}\n```"
        assert decomposer._extract_json(content) == '{"key": "value"}'

        # Plain JSON
        content = '{"key": "value"}'
        assert decomposer._extract_json(content) == '{"key": "value"}'


class TestPlanRefiner:
    """Tests for PlanRefiner."""

    @pytest.fixture
    def mock_llm(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_refine_success(self, mock_llm):
        """Test successful plan refinement."""
        response_content = '''{"approach": "alternative", "reasoning": "Try different method", "new_tasks": [
            {"id": "task_alt", "description": "Try alternative approach", "dependencies": []}
        ]}'''

        mock_llm.chat.return_value = LLMResponse(content=response_content, model="test")

        refiner = PlanRefiner(mock_llm)

        plan = Plan(id="plan_1", goal="Test goal")
        plan.add_task(Task(id="task_1", description="Failed task"))

        new_tasks = await refiner.refine(plan, "task_1", "Connection timeout")

        assert len(new_tasks) == 1
        assert new_tasks[0].id == "task_alt"

    @pytest.mark.asyncio
    async def test_refine_task_not_found(self, mock_llm):
        """Test refinement with non-existent task."""
        refiner = PlanRefiner(mock_llm)
        plan = Plan(id="plan_1", goal="Test goal")

        with pytest.raises(ValueError, match="not found"):
            await refiner.refine(plan, "nonexistent", "Error")

    @pytest.mark.asyncio
    async def test_refine_llm_error_returns_empty(self, mock_llm):
        """Test refinement returns empty list on LLM error."""
        mock_llm.chat.side_effect = Exception("LLM failed")

        refiner = PlanRefiner(mock_llm)
        plan = Plan(id="plan_1", goal="Test goal")
        plan.add_task(Task(id="task_1", description="Failed task"))

        new_tasks = await refiner.refine(plan, "task_1", "Error")

        assert new_tasks == []


class TestPlanningEngine:
    """Tests for PlanningEngine."""

    @pytest.fixture
    def mock_agent_engine(self):
        engine = MagicMock()
        engine.llm_client = AsyncMock()
        return engine

    @pytest.mark.asyncio
    async def test_should_plan_disabled(self, mock_agent_engine):
        """Test returns False when planning is disabled."""
        config = PlanningConfig(enabled=False)
        engine = PlanningEngine(mock_agent_engine, config)

        result = await engine.should_plan("Some complex task")
        assert result is False

    @pytest.mark.asyncio
    async def test_should_plan_auto_detect_disabled(self, mock_agent_engine):
        """Test returns False when auto-detect is disabled."""
        config = PlanningConfig(auto_detect=False)
        engine = PlanningEngine(mock_agent_engine, config)

        result = await engine.should_plan("Some task")
        assert result is False

    @pytest.mark.asyncio
    async def test_should_plan_uses_classifier(self, mock_agent_engine):
        """Test uses intent classifier."""
        mock_agent_engine.llm_client.chat.return_value = LLMResponse(
            content="TRUE", model="test"
        )

        engine = PlanningEngine(mock_agent_engine)
        result = await engine.should_plan("Complex multi-step task")

        assert result is True

    @pytest.mark.asyncio
    async def test_create_plan_success(self, mock_agent_engine):
        """Test successful plan creation."""
        response_content = '''{"tasks": [
            {"id": "task_1", "description": "Step 1", "dependencies": []},
            {"id": "task_2", "description": "Step 2", "dependencies": ["task_1"]}
        ]}'''

        mock_agent_engine.llm_client.chat.return_value = LLMResponse(
            content=response_content, model="test"
        )

        engine = PlanningEngine(mock_agent_engine)
        plan = await engine.create_plan("Do something complex")

        assert plan.goal == "Do something complex"
        assert len(plan.tasks) == 2
        assert "task_1" in plan.tasks
        assert "task_2" in plan.tasks

    @pytest.mark.asyncio
    async def test_create_plan_no_llm(self):
        """Test error when no LLM available."""
        engine = PlanningEngine(agent_engine=None)

        with pytest.raises(RuntimeError, match="No LLM"):
            await engine.create_plan("Goal")

    @pytest.mark.asyncio
    async def test_create_plan_empty_tasks(self, mock_agent_engine):
        """Test error when no tasks generated."""
        mock_agent_engine.llm_client.chat.return_value = LLMResponse(
            content='{"tasks": []}',
            model="test"
        )

        engine = PlanningEngine(mock_agent_engine)

        with pytest.raises(PlanCreationError, match="No tasks generated"):
            await engine.create_plan("Goal")

    @pytest.mark.asyncio
    async def test_refine_plan(self, mock_agent_engine):
        """Test plan refinement."""
        refinement_response = '''{"approach": "alternative", "reasoning": "Retry with timeout", "new_tasks": [
            {"id": "task_retry", "description": "Retry with longer timeout", "dependencies": []}
        ]}'''

        mock_agent_engine.llm_client.chat.return_value = LLMResponse(
            content=refinement_response, model="test"
        )

        engine = PlanningEngine(mock_agent_engine)

        plan = Plan(id="plan_1", goal="Test")
        plan.add_task(Task(id="task_1", description="Failed"))

        refined = await engine.refine_plan(plan, "task_1", "Timeout error")

        assert len(refined.tasks) == 2  # Original + new
        assert "task_retry" in refined.tasks

    @pytest.mark.asyncio
    async def test_refine_plan_no_refiner(self, mock_agent_engine):
        """Test returns original plan when no refiner available."""
        engine = PlanningEngine(None)  # No LLM, no refiner

        plan = Plan(id="plan_1", goal="Test")
        plan.add_task(Task(id="task_1", description="Failed"))

        refined = await engine.refine_plan(plan, "task_1", "Error")

        assert refined is plan

    def test_set_llm_client(self, mock_agent_engine):
        """Test updating LLM client."""
        engine = PlanningEngine(mock_agent_engine)
        new_llm = AsyncMock()

        engine.set_llm_client(new_llm)

        assert engine.classifier.llm_client is new_llm
        assert engine.decomposer is not None
        assert engine.refiner is not None
