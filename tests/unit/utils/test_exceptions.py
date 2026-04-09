"""Tests for exceptions module."""

import pytest

from persona_agent.utils.exceptions import (
    APIRateLimitError,
    AuthenticationError,
    ConfigurationError,
    ConversationNotFoundError,
    InvalidMoodError,
    LLMError,
    MemoryStoreError,
    MoodEngineError,
    PersonaAgentError,
    SkillError,
    SkillExecutionError,
    SkillNotFoundError,
    UserNotFoundError,
    ValidationError,
)


class TestPersonaAgentError:
    """Tests for base PersonaAgentError class."""

    def test_basic_error(self):
        """Test basic error creation."""
        error = PersonaAgentError("Test message")

        assert str(error) == "[UNKNOWN_ERROR] Test message"
        assert error.message == "Test message"
        assert error.code == "UNKNOWN_ERROR"
        assert error.details == {}

    def test_error_with_code(self):
        """Test error with custom code."""
        error = PersonaAgentError("Test message", code="CUSTOM_ERROR")

        assert error.code == "CUSTOM_ERROR"
        assert str(error) == "[CUSTOM_ERROR] Test message"

    def test_error_with_details(self):
        """Test error with details."""
        error = PersonaAgentError("Test message", code="CUSTOM_ERROR", details={"key": "value"})

        assert error.details == {"key": "value"}
        assert "Details:" in str(error)
        assert "key" in str(error)

    def test_error_inheritance(self):
        """Test that all errors inherit from PersonaAgentError."""
        errors = [
            ConfigurationError("test"),
            ValidationError("test"),
            MemoryStoreError("test"),
            UserNotFoundError("user123"),
            ConversationNotFoundError("conv123"),
            LLMError("test"),
            APIRateLimitError("openai"),
            AuthenticationError("openai"),
            SkillError("test"),
            SkillNotFoundError("skill"),
            SkillExecutionError("skill", ValueError("original")),
            MoodEngineError("test"),
            InvalidMoodError("mood"),
        ]

        for error in errors:
            assert isinstance(error, PersonaAgentError)


class TestConfigurationError:
    """Tests for ConfigurationError."""

    def test_basic_config_error(self):
        """Test basic configuration error."""
        error = ConfigurationError("Invalid config")

        assert error.code == "CONFIG_ERROR"
        assert "Invalid config" in str(error)

    def test_config_error_with_file(self):
        """Test configuration error with file path."""
        error = ConfigurationError("Invalid YAML", file_path="/path/to/config.yaml")

        assert error.details["file_path"] == "/path/to/config.yaml"
        assert "file_path" in str(error)

    def test_config_error_with_extra_kwargs(self):
        """Test configuration error with extra kwargs."""
        error = ConfigurationError(
            "Invalid config", file_path="/path/to/config.yaml", line=10, column=5
        )

        assert error.details["line"] == 10
        assert error.details["column"] == 5


class TestValidationError:
    """Tests for ValidationError."""

    def test_basic_validation_error(self):
        """Test basic validation error."""
        error = ValidationError("Field is required")

        assert error.code == "VALIDATION_ERROR"

    def test_validation_error_with_field(self):
        """Test validation error with field name."""
        error = ValidationError("Invalid value", field="username")

        assert error.details["field"] == "username"

    def test_validation_error_with_multiple_fields(self):
        """Test validation error with multiple invalid fields."""
        error = ValidationError(
            "Multiple validation errors",
            field="data",
            fields=["username", "email"],
        )

        assert error.details["field"] == "data"
        assert "fields" in error.details


class TestMemoryStoreError:
    """Tests for MemoryStoreError."""

    def test_basic_memory_error(self):
        """Test basic memory store error."""
        error = MemoryStoreError("Database connection failed")

        assert error.code == "MEMORY_ERROR"

    def test_memory_error_with_operation(self):
        """Test memory error with operation context."""
        error = MemoryStoreError("Failed to save", operation="store", session_id="test123")

        assert error.details["operation"] == "store"
        assert error.details["session_id"] == "test123"


class TestUserNotFoundError:
    """Tests for UserNotFoundError."""

    def test_user_not_found(self):
        """Test user not found error."""
        error = UserNotFoundError("user123")

        assert error.code == "USER_NOT_FOUND"
        assert "user123" in str(error)
        assert error.details["user_id"] == "user123"
        assert error.details["operation"] == "get_user"


class TestConversationNotFoundError:
    """Tests for ConversationNotFoundError."""

    def test_conversation_not_found(self):
        """Test conversation not found error."""
        error = ConversationNotFoundError("conv456")

        assert error.code == "CONVERSATION_NOT_FOUND"
        assert "conv456" in str(error)
        assert error.details["conversation_id"] == "conv456"


class TestLLMError:
    """Tests for LLMError."""

    def test_basic_llm_error(self):
        """Test basic LLM error."""
        error = LLMError("API request failed")

        assert error.code == "LLM_ERROR"

    def test_llm_error_with_provider(self):
        """Test LLM error with provider."""
        error = LLMError("Rate limited", provider="openai")

        assert error.details["provider"] == "openai"

    def test_llm_error_with_status_code(self):
        """Test LLM error with HTTP status code."""
        error = LLMError("Bad request", provider="openai", status_code=400, response="Invalid JSON")

        assert error.details["status_code"] == 400
        assert error.details["response"] == "Invalid JSON"


class TestAPIRateLimitError:
    """Tests for APIRateLimitError."""

    def test_rate_limit_without_retry(self):
        """Test rate limit error without retry after."""
        error = APIRateLimitError("openai")

        assert error.code == "RATE_LIMIT_ERROR"
        assert "openai" in str(error)
        assert error.details["retry_after"] is None

    def test_rate_limit_with_retry(self):
        """Test rate limit error with retry after."""
        error = APIRateLimitError("openai", retry_after=60)

        assert "60 seconds" in str(error)
        assert error.details["retry_after"] == 60


class TestAuthenticationError:
    """Tests for AuthenticationError."""

    def test_auth_error(self):
        """Test authentication error."""
        error = AuthenticationError("anthropic")

        assert error.code == "AUTH_ERROR"
        assert "anthropic" in str(error)
        assert error.details["provider"] == "anthropic"


class TestSkillErrors:
    """Tests for skill-related errors."""

    def test_skill_error(self):
        """Test basic skill error."""
        error = SkillError("Skill initialization failed")

        assert error.code == "SKILL_ERROR"

    def test_skill_error_with_name(self):
        """Test skill error with skill name."""
        error = SkillError("Execution failed", skill_name="weather_skill")

        assert error.details["skill_name"] == "weather_skill"

    def test_skill_not_found(self):
        """Test skill not found error."""
        error = SkillNotFoundError("nonexistent_skill")

        assert error.code == "SKILL_NOT_FOUND"
        assert "nonexistent_skill" in str(error)

    def test_skill_execution_error(self):
        """Test skill execution error."""
        original_error = ValueError("Invalid input")
        error = SkillExecutionError("weather_skill", original_error)

        assert error.code == "SKILL_EXECUTION_ERROR"
        assert "weather_skill" in str(error)
        assert "ValueError" in str(error)
        assert error.details["original_error_type"] == "ValueError"

    def test_skill_execution_error_with_context(self):
        """Test skill execution error with additional context."""
        original_error = RuntimeError("Timeout")
        error = SkillExecutionError("api_skill", original_error, endpoint="/api/data", timeout=30)

        assert error.details["endpoint"] == "/api/data"
        assert error.details["timeout"] == 30


class TestMoodErrors:
    """Tests for mood-related errors."""

    def test_mood_engine_error(self):
        """Test mood engine error."""
        error = MoodEngineError("Invalid transition")

        assert error.code == "MOOD_ERROR"

    def test_mood_engine_error_with_name(self):
        """Test mood engine error with mood name."""
        error = MoodEngineError("Cannot activate", mood_name="ANGRY")

        assert error.details["mood_name"] == "ANGRY"

    def test_invalid_mood_without_valid_moods(self):
        """Test invalid mood error without valid moods list."""
        error = InvalidMoodError("UNKNOWN_MOOD")

        assert error.code == "INVALID_MOOD"
        assert "UNKNOWN_MOOD" in str(error)

    def test_invalid_mood_with_valid_moods(self):
        """Test invalid mood error with valid moods list."""
        valid_moods = ["HAPPY", "SAD", "ANGRY"]
        error = InvalidMoodError("UNKNOWN", valid_moods=valid_moods)

        assert "HAPPY" in str(error)
        assert "SAD" in str(error)
        assert "ANGRY" in str(error)
        assert error.details["valid_moods"] == valid_moods


class TestExceptionChaining:
    """Tests for exception chaining behavior."""

    def test_catch_base_exception(self):
        """Test that all exceptions can be caught with base class."""
        exceptions_to_test = [
            ConfigurationError("test"),
            ValidationError("test"),
            MemoryStoreError("test"),
            LLMError("test"),
            SkillError("test"),
            MoodEngineError("test"),
        ]

        for exc in exceptions_to_test:
            try:
                raise exc
            except PersonaAgentError as caught:
                assert caught is exc

    def test_specific_exception_catching(self):
        """Test catching specific exception types."""
        with pytest.raises(ConfigurationError):
            raise ConfigurationError("test")

        with pytest.raises(ValidationError):
            raise ValidationError("test")

        with pytest.raises(LLMError):
            raise LLMError("test")


class TestErrorMessageFormatting:
    """Tests for error message formatting."""

    def test_message_without_details(self):
        """Test message format when no details present."""
        error = PersonaAgentError("Simple message", code="TEST")

        assert str(error) == "[TEST] Simple message"

    def test_message_with_empty_details(self):
        """Test message format when details dict is empty."""
        error = PersonaAgentError("Simple message", code="TEST", details={})

        assert str(error) == "[TEST] Simple message"

    def test_message_with_details(self):
        """Test message format when details are present."""
        error = PersonaAgentError("Error occurred", code="TEST", details={"key": "value"})

        message = str(error)
        assert "[TEST] Error occurred" in message
        assert "Details:" in message
