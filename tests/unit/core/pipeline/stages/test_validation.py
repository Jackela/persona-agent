from unittest.mock import MagicMock, patch

import pytest

from persona_agent.core.pipeline.context import ChatContext, StageResult
from persona_agent.core.pipeline.stages.validation import ValidationStage


class TestValidationStage:
    """Test suite for ValidationStage."""

    @pytest.fixture
    def mock_llm_client(self):
        return MagicMock()

    @pytest.fixture
    def chat_context(self):
        return ChatContext(user_input="hello", session_id="test-session")

    @pytest.mark.asyncio
    async def test_sets_correlation_id(self, mock_llm_client, chat_context):
        stage = ValidationStage(llm_client=mock_llm_client)
        await stage.process(chat_context)

        assert chat_context.correlation_id is not None
        assert isinstance(chat_context.correlation_id, str)
        assert len(chat_context.correlation_id) > 0

    @pytest.mark.asyncio
    async def test_raises_runtime_error_without_llm_client(self, chat_context):
        stage = ValidationStage(llm_client=None)

        with pytest.raises(RuntimeError, match="LLM client not configured"):
            await stage.process(chat_context)

    @pytest.mark.asyncio
    async def test_calls_set_correlation_id(self, mock_llm_client, chat_context):
        stage = ValidationStage(llm_client=mock_llm_client)

        with patch("persona_agent.core.pipeline.stages.validation.set_correlation_id") as mock_set:
            await stage.process(chat_context)

            mock_set.assert_called_once_with(chat_context.correlation_id)

    @pytest.mark.asyncio
    async def test_allows_continuation(self, mock_llm_client, chat_context):
        stage = ValidationStage(llm_client=mock_llm_client)
        result = await stage.process(chat_context)

        assert isinstance(result, StageResult)
        assert result.should_continue is True
        assert result.context is chat_context
