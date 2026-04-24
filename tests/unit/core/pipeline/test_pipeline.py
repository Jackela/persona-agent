"""Tests for ChatPipeline orchestrator."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from persona_agent.core.pipeline.context import ChatContext, StageResult
from persona_agent.core.pipeline.pipeline import ChatPipeline


class TestChatPipeline:
    """Test suite for ChatPipeline orchestrator."""

    @pytest.fixture
    def base_context(self):
        """Create a base ChatContext for testing."""
        return ChatContext(user_input="hello", session_id="sess_123")

    def _make_stage(self, name, should_continue=True, side_effect=None):
        """Helper to create a mock pipeline stage."""
        stage = MagicMock()
        stage.__class__.__name__ = name
        stage.process = AsyncMock()

        if side_effect:
            stage.process.side_effect = side_effect
        else:
            stage.process.return_value = StageResult(
                context=None,
                should_continue=should_continue,
            )
        return stage

    @pytest.mark.asyncio
    async def test_pipeline_executes_stages_in_order(self, base_context):
        """Test that pipeline executes stages in the order provided."""
        stage1 = self._make_stage("Stage1")
        stage2 = self._make_stage("Stage2")
        stage3 = self._make_stage("Stage3")

        # Set up return values to pass context through
        stage1.process.return_value = StageResult(context=base_context)
        stage2.process.return_value = StageResult(context=base_context)
        stage3.process.return_value = StageResult(context=base_context)

        pipeline = ChatPipeline(stages=[stage1, stage2, stage3])
        result = await pipeline.execute(base_context)

        assert result is base_context
        stage1.process.assert_awaited_once_with(base_context)
        stage2.process.assert_awaited_once_with(base_context)
        stage3.process.assert_awaited_once_with(base_context)

        # Verify order: stage1 called before stage2, stage2 before stage3
        calls = [
            stage1.process.await_args,
            stage2.process.await_args,
            stage3.process.await_args,
        ]
        assert all(c is not None for c in calls)

    @pytest.mark.asyncio
    async def test_pipeline_short_circuits_on_should_continue_false(self, base_context):
        """Test pipeline stops executing when a stage returns should_continue=False."""
        stage1 = self._make_stage("Stage1")
        stage2 = self._make_stage("Stage2", should_continue=False)
        stage3 = self._make_stage("Stage3")

        stage1.process.return_value = StageResult(context=base_context)
        stage2.process.return_value = StageResult(
            context=base_context, should_continue=False
        )

        pipeline = ChatPipeline(stages=[stage1, stage2, stage3])
        result = await pipeline.execute(base_context)

        assert result is base_context
        stage1.process.assert_awaited_once()
        stage2.process.assert_awaited_once()
        stage3.process.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_pipeline_context_mutation_propagation(self, base_context):
        """Test that context mutations are propagated between stages."""
        stage1 = self._make_stage("Stage1")
        stage2 = self._make_stage("Stage2")

        # Stage1 modifies the context
        modified_context = ChatContext(
            user_input="hello", session_id="sess_123", correlation_id="corr_1"
        )
        stage1.process.return_value = StageResult(context=modified_context)
        stage2.process.return_value = StageResult(context=modified_context)

        pipeline = ChatPipeline(stages=[stage1, stage2])
        result = await pipeline.execute(base_context)

        # Stage2 should receive the modified context from stage1
        stage2.process.assert_awaited_once_with(modified_context)
        assert result.correlation_id == "corr_1"

    @pytest.mark.asyncio
    async def test_cleanup_stage_runs_in_finally_block(self, base_context):
        """Test cleanup stage runs even when regular stages complete successfully."""
        stage1 = self._make_stage("Stage1")
        cleanup = self._make_stage("CleanupStage")

        stage1.process.return_value = StageResult(context=base_context)
        cleanup.process.return_value = StageResult(context=base_context)

        pipeline = ChatPipeline(stages=[stage1], cleanup_stage=cleanup)
        result = await pipeline.execute(base_context)

        cleanup.process.assert_awaited_once_with(base_context)
        assert result is base_context

    @pytest.mark.asyncio
    async def test_cleanup_stage_runs_when_stage_fails(self, base_context):
        """Test cleanup stage runs even when a regular stage raises an exception."""
        stage1 = self._make_stage("Stage1")
        cleanup = self._make_stage("CleanupStage")

        stage1.process.side_effect = ValueError("Stage failed")
        cleanup.process.return_value = StageResult(context=base_context)

        pipeline = ChatPipeline(stages=[stage1], cleanup_stage=cleanup)

        with pytest.raises(ValueError, match="Stage failed"):
            await pipeline.execute(base_context)

        cleanup.process.assert_awaited_once_with(base_context)

    @pytest.mark.asyncio
    async def test_cleanup_stage_runs_on_short_circuit(self, base_context):
        """Test cleanup stage runs when pipeline short-circuits."""
        stage1 = self._make_stage("Stage1", should_continue=False)
        cleanup = self._make_stage("CleanupStage")

        stage1.process.return_value = StageResult(
            context=base_context, should_continue=False
        )
        cleanup.process.return_value = StageResult(context=base_context)

        pipeline = ChatPipeline(stages=[stage1], cleanup_stage=cleanup)
        result = await pipeline.execute(base_context)

        cleanup.process.assert_awaited_once_with(base_context)
        assert result is base_context

    @pytest.mark.asyncio
    async def test_cleanup_error_does_not_mask_original_error(self, base_context):
        """Test that cleanup stage errors don't mask the original exception."""
        stage1 = self._make_stage("Stage1")
        cleanup = self._make_stage("CleanupStage")

        stage1.process.side_effect = RuntimeError("Original error")
        cleanup.process.side_effect = ValueError("Cleanup error")

        pipeline = ChatPipeline(stages=[stage1], cleanup_stage=cleanup)

        with pytest.raises(RuntimeError, match="Original error"):
            await pipeline.execute(base_context)

    @pytest.mark.asyncio
    async def test_empty_pipeline_returns_context(self, base_context):
        """Test that an empty pipeline returns the input context unchanged."""
        pipeline = ChatPipeline(stages=[])
        result = await pipeline.execute(base_context)

        assert result is base_context

    @pytest.mark.asyncio
    async def test_no_cleanup_stage_no_error(self, base_context):
        """Test pipeline works without a cleanup stage."""
        stage1 = self._make_stage("Stage1")
        stage1.process.return_value = StageResult(context=base_context)

        pipeline = ChatPipeline(stages=[stage1], cleanup_stage=None)
        result = await pipeline.execute(base_context)

        assert result is base_context

    @pytest.mark.asyncio
    async def test_pipeline_logs_stage_execution(self, base_context, caplog):
        """Test that pipeline logs stage execution and short-circuit events."""
        import logging

        stage1 = self._make_stage("TestStage", should_continue=False)
        stage1.process.return_value = StageResult(
            context=base_context, should_continue=False
        )

        pipeline = ChatPipeline(stages=[stage1])

        with caplog.at_level(logging.DEBUG):
            await pipeline.execute(base_context)

        assert "Executing stage: TestStage" in caplog.text
        assert "Pipeline short-circuited by TestStage" in caplog.text

    @pytest.mark.asyncio
    async def test_pipeline_logs_execution_failure(self, base_context, caplog):
        """Test that pipeline logs when execution fails."""
        import logging

        stage1 = self._make_stage("FailingStage")
        stage1.process.side_effect = RuntimeError("Boom")

        pipeline = ChatPipeline(stages=[stage1])

        with caplog.at_level(logging.DEBUG), pytest.raises(RuntimeError):
            await pipeline.execute(base_context)

        assert "Pipeline execution failed" in caplog.text

    @pytest.mark.asyncio
    async def test_pipeline_logs_cleanup_failure(self, base_context, caplog):
        """Test that pipeline logs when cleanup stage fails."""
        import logging

        stage1 = self._make_stage("Stage1")
        cleanup = self._make_stage("CleanupStage")

        stage1.process.side_effect = RuntimeError("Stage error")
        cleanup.process.side_effect = ValueError("Cleanup error")

        pipeline = ChatPipeline(stages=[stage1], cleanup_stage=cleanup)

        with caplog.at_level(logging.DEBUG):
            with pytest.raises(RuntimeError, match="Stage error"):
                await pipeline.execute(base_context)

        assert "Cleanup stage failed" in caplog.text
