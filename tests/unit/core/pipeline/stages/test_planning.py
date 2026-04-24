"""Tests for PlanningExecutionStage."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from persona_agent.core.pipeline.context import ChatContext, StageResult
from persona_agent.core.pipeline.stages.planning import PlanningExecutionStage
from persona_agent.core.planning import PlanningEngine
from persona_agent.core.planning.executor import PlanExecutor
from persona_agent.core.planning.models import Plan


class TestPlanningExecutionStage:
    """Test suite for PlanningExecutionStage."""

    @pytest.fixture
    def mock_planning_engine(self):
        """Create a mock PlanningEngine."""
        engine = MagicMock(spec=PlanningEngine)
        engine.should_plan = AsyncMock()
        engine.create_plan = AsyncMock()
        return engine

    @pytest.fixture
    def mock_plan_executor(self):
        """Create a mock PlanExecutor."""
        executor = MagicMock(spec=PlanExecutor)
        executor.execute_plan = AsyncMock()
        return executor

    @pytest.fixture
    def stage(self, mock_planning_engine, mock_plan_executor):
        """Create a PlanningExecutionStage instance with mocked dependencies."""
        return PlanningExecutionStage(
            planning_engine=mock_planning_engine,
            plan_executor=mock_plan_executor,
        )

    @pytest.fixture
    def chat_context(self):
        """Create a ChatContext for testing."""
        return ChatContext(
            user_input="test input",
            session_id="session_123",
            enable_planning=True,
        )

    @pytest.fixture
    def mock_plan(self):
        """Create a mock Plan."""
        plan = MagicMock(spec=Plan)
        plan.id = "plan_123"
        return plan

    @pytest.mark.asyncio
    async def test_short_circuits_when_planning_needed(
        self, stage, mock_planning_engine, mock_plan_executor, chat_context, mock_plan
    ):
        """Test that stage short-circuits when planning is needed and executed."""
        # Arrange
        mock_planning_engine.should_plan.return_value = True
        mock_planning_engine.create_plan.return_value = mock_plan
        mock_plan_executor.execute_plan.return_value = {
            "status": "completed",
            "completed_tasks": ["task_1"],
            "outputs": {"task_1": "Task output"},
        }

        # Act
        result = await stage.process(chat_context)

        # Assert
        assert isinstance(result, StageResult)
        assert result.should_continue is False
        assert chat_context.is_complete is True
        assert "completed your request" in chat_context.response
        mock_planning_engine.should_plan.assert_called_once_with("test input")
        mock_planning_engine.create_plan.assert_called_once()
        mock_plan_executor.execute_plan.assert_called_once()

    @pytest.mark.asyncio
    async def test_continues_when_planning_not_needed(
        self, stage, mock_planning_engine, chat_context
    ):
        """Test that stage continues when planning is not needed."""
        # Arrange
        mock_planning_engine.should_plan.return_value = False

        # Act
        result = await stage.process(chat_context)

        # Assert
        assert isinstance(result, StageResult)
        assert result.should_continue is True
        assert chat_context.is_complete is False
        mock_planning_engine.create_plan.assert_not_called()

    @pytest.mark.asyncio
    async def test_continues_when_planning_disabled(
        self, stage, mock_planning_engine, chat_context
    ):
        """Test that stage continues when planning is disabled."""
        # Arrange
        chat_context.enable_planning = False

        # Act
        result = await stage.process(chat_context)

        # Assert
        assert isinstance(result, StageResult)
        assert result.should_continue is True
        assert chat_context.is_complete is False
        mock_planning_engine.should_plan.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_plan_execution_errors(
        self, stage, mock_planning_engine, mock_plan_executor, chat_context, mock_plan
    ):
        """Test that stage handles plan execution errors gracefully."""
        # Arrange
        mock_planning_engine.should_plan.return_value = True
        mock_planning_engine.create_plan.return_value = mock_plan
        mock_plan_executor.execute_plan.side_effect = Exception("Execution failed")

        # Act
        result = await stage.process(chat_context)

        # Assert
        assert isinstance(result, StageResult)
        assert result.should_continue is False
        assert chat_context.is_complete is True
        assert "encountered an error" in chat_context.response
        assert "Execution failed" in chat_context.response

    @pytest.mark.asyncio
    async def test_formats_completed_results(
        self, stage, mock_planning_engine, mock_plan_executor, chat_context, mock_plan
    ):
        """Test that completed plan results are formatted correctly."""
        # Arrange
        mock_planning_engine.should_plan.return_value = True
        mock_planning_engine.create_plan.return_value = mock_plan
        mock_plan_executor.execute_plan.return_value = {
            "status": "completed",
            "completed_tasks": ["task_1", "task_2"],
            "outputs": {
                "task_1": "First task output",
                "task_2": "Second task output",
            },
        }

        # Act
        result = await stage.process(chat_context)

        # Assert
        assert isinstance(result, StageResult)
        assert result.should_continue is False
        assert "completed your request" in chat_context.response
        assert "task_1" in chat_context.response
        assert "First task output" in chat_context.response
        assert "task_2" in chat_context.response
        assert "Second task output" in chat_context.response

    @pytest.mark.asyncio
    async def test_formats_failed_results(
        self, stage, mock_planning_engine, mock_plan_executor, chat_context, mock_plan
    ):
        """Test that failed plan results are formatted correctly."""
        # Arrange
        mock_planning_engine.should_plan.return_value = True
        mock_planning_engine.create_plan.return_value = mock_plan
        mock_plan_executor.execute_plan.return_value = {
            "status": "failed",
            "completed_tasks": ["task_1"],
            "failed_tasks": ["task_2"],
            "outputs": {
                "task_1": "Completed task output that is long enough",
                "task_2": "Error message for failed task",
            },
        }

        # Act
        result = await stage.process(chat_context)

        # Assert
        assert isinstance(result, StageResult)
        assert result.should_continue is False
        assert "encountered some issues" in chat_context.response
        assert "task_1" in chat_context.response
        assert "task_2" in chat_context.response
        assert "Error message for failed task" in chat_context.response

    @pytest.mark.asyncio
    async def test_active_plans_tracking(
        self, stage, mock_planning_engine, mock_plan_executor, chat_context, mock_plan
    ):
        """Test that active plans are tracked during execution."""
        # Arrange
        mock_planning_engine.should_plan.return_value = True
        mock_planning_engine.create_plan.return_value = mock_plan
        mock_plan_executor.execute_plan.return_value = {
            "status": "completed",
            "completed_tasks": ["task_1"],
            "outputs": {"task_1": "output"},
        }

        # Act
        await stage.process(chat_context)

        # Assert
        assert mock_plan.id not in stage._active_plans

    @pytest.mark.asyncio
    async def test_unknown_status_formatting(
        self, stage, mock_planning_engine, mock_plan_executor, chat_context, mock_plan
    ):
        """Test formatting when plan returns unknown status."""
        # Arrange
        mock_planning_engine.should_plan.return_value = True
        mock_planning_engine.create_plan.return_value = mock_plan
        mock_plan_executor.execute_plan.return_value = {
            "status": "unknown_status",
        }

        # Act
        result = await stage.process(chat_context)

        # Assert
        assert isinstance(result, StageResult)
        assert result.should_continue is False
        assert "unknown status" in chat_context.response

    @pytest.mark.asyncio
    async def test_plan_context_includes_session_id(
        self, stage, mock_planning_engine, mock_plan_executor, chat_context, mock_plan
    ):
        """Test that plan context includes session_id."""
        # Arrange
        mock_planning_engine.should_plan.return_value = True
        mock_planning_engine.create_plan.return_value = mock_plan
        mock_plan_executor.execute_plan.return_value = {
            "status": "completed",
            "completed_tasks": [],
            "outputs": {},
        }

        # Act
        await stage.process(chat_context)

        # Assert
        call_args = mock_planning_engine.create_plan.call_args
        assert call_args[0][1]["session_id"] == "session_123"
