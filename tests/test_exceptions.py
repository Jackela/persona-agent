"""Tests for custom exceptions."""

from persona_agent.utils.exceptions import (
    APIRateLimitError,
    AuthenticationError,
    ConfigurationError,
    ConversationNotFoundError,
    FileNotFoundError,
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


class TestBaseException:
    """Test PersonaAgentError base class."""

    def test_basic_error(self) -> None:
        """Test creating a basic error."""
        error = PersonaAgentError("Something went wrong")
        assert error.message == "Something went wrong"
        assert error.code == "UNKNOWN_ERROR"
        assert str(error) == "[UNKNOWN_ERROR] Something went wrong"

    def test_error_with_code(self) -> None:
        """Test error with custom code."""
        error = PersonaAgentError("Failed", code="CUSTOM_ERROR")
        assert error.code == "CUSTOM_ERROR"
        assert "CUSTOM_ERROR" in str(error)

    def test_error_with_details(self) -> None:
        """Test error with additional details."""
        error = PersonaAgentError("Failed", code="TEST_ERROR", details={"key": "value"})
        assert error.details == {"key": "value"}
        assert "key" in str(error)


class TestConfigurationErrors:
    """Test configuration-related exceptions."""

    def test_configuration_error(self) -> None:
        """Test ConfigurationError."""
        error = ConfigurationError("Invalid config", file_path="/path/to/config")
        assert error.code == "CONFIG_ERROR"
        assert "/path/to/config" in str(error)

    def test_validation_error(self) -> None:
        """Test ValidationError."""
        error = ValidationError("Invalid field", field="name")
        assert error.code == "VALIDATION_ERROR"
        assert "name" in str(error)

    def test_file_not_found_error(self) -> None:
        """Test FileNotFoundError."""
        error = FileNotFoundError("/missing/file.yaml")
        assert error.code == "FILE_NOT_FOUND"
        assert "/missing/file.yaml" in error.message


class TestMemoryStoreErrors:
    """Test memory store exceptions."""

    def test_memory_store_error(self) -> None:
        """Test MemoryStoreError."""
        error = MemoryStoreError("Database error", operation="insert")
        assert error.code == "MEMORY_ERROR"
        assert "insert" in str(error)

    def test_user_not_found_error(self) -> None:
        """Test UserNotFoundError."""
        error = UserNotFoundError("user_123")
        assert error.code == "USER_NOT_FOUND"
        assert "user_123" in error.message

    def test_conversation_not_found_error(self) -> None:
        """Test ConversationNotFoundError."""
        error = ConversationNotFoundError("conv_456")
        assert error.code == "CONVERSATION_NOT_FOUND"
        assert "conv_456" in error.message


class TestLLMErrors:
    """Test LLM-related exceptions."""

    def test_llm_error(self) -> None:
        """Test LLMError."""
        error = LLMError("API failed", provider="openai")
        assert error.code == "LLM_ERROR"
        assert "openai" in str(error)

    def test_rate_limit_error(self) -> None:
        """Test APIRateLimitError."""
        error = APIRateLimitError("openai", retry_after=60)
        assert error.code == "RATE_LIMIT_ERROR"
        assert "60" in error.message
        assert "openai" in error.message

    def test_authentication_error(self) -> None:
        """Test AuthenticationError."""
        error = AuthenticationError("anthropic")
        assert error.code == "AUTH_ERROR"
        assert "anthropic" in error.message


class TestSkillErrors:
    """Test skill system exceptions."""

    def test_skill_error(self) -> None:
        """Test SkillError."""
        error = SkillError("Skill failed", skill_name="weather")
        assert error.code == "SKILL_ERROR"
        assert "weather" in str(error)

    def test_skill_not_found_error(self) -> None:
        """Test SkillNotFoundError."""
        error = SkillNotFoundError("nonexistent_skill")
        assert error.code == "SKILL_NOT_FOUND"
        assert "nonexistent_skill" in error.message

    def test_skill_execution_error(self) -> None:
        """Test SkillExecutionError."""
        original = ValueError("Something broke")
        error = SkillExecutionError("my_skill", original)
        assert error.code == "SKILL_EXECUTION_ERROR"
        assert "my_skill" in error.message
        assert "ValueError" in str(error)


class TestMoodEngineErrors:
    """Test mood engine exceptions."""

    def test_mood_engine_error(self) -> None:
        """Test MoodEngineError."""
        error = MoodEngineError("Invalid transition", mood_name="happy")
        assert error.code == "MOOD_ERROR"
        assert "happy" in str(error)

    def test_invalid_mood_error(self) -> None:
        """Test InvalidMoodError."""
        error = InvalidMoodError("angry", valid_moods=["happy", "sad"])
        assert error.code == "INVALID_MOOD"
        assert "angry" in error.message
        assert "happy" in error.message
        assert "sad" in error.message


class TestExceptionHierarchy:
    """Test exception inheritance hierarchy."""

    def test_all_inherit_base(self) -> None:
        """Test all exceptions inherit from PersonaAgentError."""
        exceptions = [
            ConfigurationError("test"),
            ValidationError("test"),
            FileNotFoundError("test"),
            MemoryStoreError("test"),
            UserNotFoundError("test"),
            ConversationNotFoundError("test"),
            LLMError("test"),
            APIRateLimitError("test"),
            AuthenticationError("test"),
            SkillError("test"),
            SkillNotFoundError("test"),
            SkillExecutionError("test", ValueError()),
            MoodEngineError("test"),
            InvalidMoodError("test"),
        ]

        for exc in exceptions:
            assert isinstance(exc, PersonaAgentError)
            assert isinstance(exc, Exception)

    def test_catch_all_persona_errors(self) -> None:
        """Test catching all errors with base class."""
        errors = [
            ConfigurationError("config issue"),
            LLMError("api issue"),
            SkillError("skill issue"),
        ]

        caught = 0
        for error in errors:
            try:
                raise error
            except PersonaAgentError:
                caught += 1

        assert caught == 3
