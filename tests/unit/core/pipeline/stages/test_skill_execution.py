"""Tests for SkillExecutionStage."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from persona_agent.core.memory_store import MemoryStore
from persona_agent.core.persona_manager import PersonaManager
from persona_agent.core.pipeline.context import ChatContext, StageResult
from persona_agent.core.pipeline.stages.skill_execution import SkillExecutionStage
from persona_agent.skills.base import SkillContext, SkillResult
from persona_agent.skills.registry import SkillRegistry


class TestSkillExecutionStage:
    """Test suite for SkillExecutionStage."""

    @pytest.fixture
    def mock_skill_registry(self):
        """Create a mock SkillRegistry."""
        registry = MagicMock(spec=SkillRegistry)
        registry.execute_matching = AsyncMock()
        return registry

    @pytest.fixture
    def mock_persona_manager(self):
        """Create a mock PersonaManager."""
        manager = MagicMock(spec=PersonaManager)
        mood_engine = MagicMock()
        mood_engine.current_state = MagicMock()
        mood_engine.current_state.name = "happy"
        manager.get_mood_engine.return_value = mood_engine
        return manager

    @pytest.fixture
    def mock_memory_store(self):
        """Create a mock MemoryStore."""
        store = MagicMock(spec=MemoryStore)
        store.store = AsyncMock()
        return store

    @pytest.fixture
    def stage(self, mock_skill_registry, mock_persona_manager, mock_memory_store):
        """Create a SkillExecutionStage instance with mocked dependencies."""
        return SkillExecutionStage(
            skill_registry=mock_skill_registry,
            persona_manager=mock_persona_manager,
            memory_store=mock_memory_store,
        )

    @pytest.fixture
    def chat_context(self):
        """Create a ChatContext for testing."""
        return ChatContext(
            user_input="test input",
            session_id="session_123",
        )

    @pytest.mark.asyncio
    async def test_short_circuits_when_skill_matches(
        self, stage, mock_skill_registry, mock_memory_store, chat_context
    ):
        """Test that stage short-circuits when a skill matches and succeeds."""
        # Arrange
        skill_result = SkillResult(success=True, response="Skill handled this")
        mock_skill_registry.execute_matching.return_value = skill_result

        # Act
        result = await stage.process(chat_context)

        # Assert
        assert isinstance(result, StageResult)
        assert result.should_continue is False
        assert chat_context.response == "Skill handled this"
        assert chat_context.is_complete is True
        mock_skill_registry.execute_matching.assert_called_once()

    @pytest.mark.asyncio
    async def test_continues_when_no_skill_matches(
        self, stage, mock_skill_registry, chat_context
    ):
        """Test that stage continues when no skill matches."""
        # Arrange
        mock_skill_registry.execute_matching.return_value = None

        # Act
        result = await stage.process(chat_context)

        # Assert
        assert isinstance(result, StageResult)
        assert result.should_continue is True
        assert chat_context.response is None
        assert chat_context.is_complete is False

    @pytest.mark.asyncio
    async def test_continues_when_skill_fails(
        self, stage, mock_skill_registry, chat_context
    ):
        """Test that stage continues when skill returns failure."""
        # Arrange
        skill_result = SkillResult(success=False, response="")
        mock_skill_registry.execute_matching.return_value = skill_result

        # Act
        result = await stage.process(chat_context)

        # Assert
        assert isinstance(result, StageResult)
        assert result.should_continue is True
        assert chat_context.response is None
        assert chat_context.is_complete is False

    @pytest.mark.asyncio
    async def test_stores_skill_response_in_memory(
        self, stage, mock_skill_registry, mock_memory_store, chat_context
    ):
        """Test that successful skill response is stored in memory."""
        # Arrange
        skill_result = SkillResult(success=True, response="Skill response")
        mock_skill_registry.execute_matching.return_value = skill_result

        # Act
        await stage.process(chat_context)

        # Assert
        mock_memory_store.store.assert_called_once_with(
            session_id="session_123",
            user_message="test input",
            assistant_message="Skill response",
        )

    @pytest.mark.asyncio
    async def test_skill_context_uses_current_mood(
        self, stage, mock_skill_registry, mock_persona_manager, chat_context
    ):
        """Test that SkillContext is created with current mood."""
        # Arrange
        skill_result = SkillResult(success=True, response="response")
        mock_skill_registry.execute_matching.return_value = skill_result

        # Act
        await stage.process(chat_context)

        # Assert
        call_args = mock_skill_registry.execute_matching.call_args[0][0]
        assert isinstance(call_args, SkillContext)
        assert call_args.current_mood == "happy"
        assert call_args.user_input == "test input"
        assert call_args.session_id == "session_123"

    @pytest.mark.asyncio
    async def test_skill_context_with_no_mood_engine(
        self, stage, mock_skill_registry, mock_persona_manager, chat_context
    ):
        """Test that SkillContext defaults to neutral when no mood engine."""
        # Arrange
        mock_persona_manager.get_mood_engine.return_value = None
        skill_result = SkillResult(success=True, response="response")
        mock_skill_registry.execute_matching.return_value = skill_result

        # Act
        await stage.process(chat_context)

        # Assert
        call_args = mock_skill_registry.execute_matching.call_args[0][0]
        assert call_args.current_mood == "neutral"
