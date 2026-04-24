"""Tests for pipeline context and result types."""

from persona_agent.core.pipeline.context import ChatContext, StageResult


class TestChatContext:
    """Test suite for ChatContext dataclass."""

    def test_chat_context_creation_with_required_fields(self):
        """Test ChatContext can be created with only required fields."""
        context = ChatContext(user_input="hello", session_id="sess_123")

        assert context.user_input == "hello"
        assert context.session_id == "sess_123"

    def test_chat_context_default_values(self):
        """Test ChatContext has correct default values for optional fields."""
        context = ChatContext(user_input="hello", session_id="sess_123")

        assert context.stream is False
        assert context.enable_planning is True
        assert context.on_plan_progress is None
        assert context.correlation_id is None
        assert context.messages == []
        assert context.response is None
        assert context.is_complete is False
        assert context.metadata == {}

    def test_chat_context_custom_values(self):
        """Test ChatContext accepts custom values for all fields."""
        context = ChatContext(
            user_input="hello",
            session_id="sess_123",
            stream=True,
            enable_planning=False,
            on_plan_progress=lambda x: x,
            correlation_id="corr_456",
            messages=[{"role": "user", "content": "hi"}],
            response="test response",
            is_complete=True,
            metadata={"key": "value"},
        )

        assert context.stream is True
        assert context.enable_planning is False
        assert context.on_plan_progress is not None
        assert context.correlation_id == "corr_456"
        assert context.messages == [{"role": "user", "content": "hi"}]
        assert context.response == "test response"
        assert context.is_complete is True
        assert context.metadata == {"key": "value"}

    def test_chat_context_mutable_state(self):
        """Test ChatContext mutable state can be modified in-place."""
        context = ChatContext(user_input="hello", session_id="sess_123")

        # Modify mutable fields
        context.messages.append({"role": "user", "content": "hello"})
        context.metadata["key"] = "value"
        context.correlation_id = "corr_789"
        context.response = "response"
        context.is_complete = True

        assert len(context.messages) == 1
        assert context.metadata["key"] == "value"
        assert context.correlation_id == "corr_789"
        assert context.response == "response"
        assert context.is_complete is True

    def test_chat_context_isolation(self):
        """Test that separate ChatContext instances don't share mutable state."""
        context1 = ChatContext(user_input="hello", session_id="sess_1")
        context2 = ChatContext(user_input="world", session_id="sess_2")

        context1.messages.append({"role": "user", "content": "msg1"})
        context1.metadata["key"] = "value1"

        assert len(context1.messages) == 1
        assert len(context2.messages) == 0
        assert "key" not in context2.metadata


class TestStageResult:
    """Test suite for StageResult dataclass."""

    def test_stage_result_default_should_continue(self):
        """Test StageResult defaults should_continue to True."""
        context = ChatContext(user_input="hello", session_id="sess_123")
        result = StageResult(context=context)

        assert result.context is context
        assert result.should_continue is True

    def test_stage_result_short_circuit(self):
        """Test StageResult can signal short-circuit with should_continue=False."""
        context = ChatContext(user_input="hello", session_id="sess_123")
        result = StageResult(context=context, should_continue=False)

        assert result.context is context
        assert result.should_continue is False

    def test_stage_result_with_modified_context(self):
        """Test StageResult carries the updated context from stage execution."""
        context = ChatContext(user_input="hello", session_id="sess_123")
        context.messages.append({"role": "assistant", "content": "response"})
        context.is_complete = True

        result = StageResult(context=context)

        assert result.context.messages == [{"role": "assistant", "content": "response"}]
        assert result.context.is_complete is True
