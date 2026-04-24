from unittest.mock import patch

import pytest

from persona_agent.core.pipeline.context import ChatContext, StageResult
from persona_agent.core.pipeline.stages.cleanup import CleanupStage


class TestCleanupStage:
    """Test suite for CleanupStage."""

    @pytest.fixture
    def chat_context(self):
        return ChatContext(user_input="hello", session_id="test-session")

    @pytest.mark.asyncio
    async def test_calls_clear_correlation_id(self, chat_context):
        stage = CleanupStage()

        with patch("persona_agent.core.pipeline.stages.cleanup.clear_correlation_id") as mock_clear:
            await stage.process(chat_context)

            mock_clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_allows_continuation(self, chat_context):
        stage = CleanupStage()
        result = await stage.process(chat_context)

        assert isinstance(result, StageResult)
        assert result.should_continue is True
        assert result.context is chat_context
