"""Shared fixtures for integration tests.

This module provides fixtures for integration testing that use real service
instances and temporary SQLite databases instead of mocked dependencies.
"""

import asyncio
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
import yaml

from persona_agent.repositories import SessionRepository
from persona_agent.services.character_service import CharacterService
from persona_agent.services.chat_service import ChatService
from persona_agent.services.session_service import SessionService
from persona_agent.utils.llm_client import LLMClient, LLMResponse

# ============================================================================
# Event Loop and Async Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Configuration and Character Fixtures
# ============================================================================


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory with test characters."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Create subdirectories
    (config_dir / "characters").mkdir()
    (config_dir / "mood_states").mkdir()
    (config_dir / "linguistic_styles").mkdir()

    return config_dir


@pytest.fixture
def create_test_character(temp_config_dir: Path) -> callable:
    """Factory fixture to create test character configs."""

    def _create_character(name: str, data: dict | None = None) -> Path:
        """Create a character config file."""
        default_data = {
            "name": f"Test {name.capitalize()}",
            "version": "1.0.0",
            "relationship": "助手",
            "traits": {
                "personality": {
                    "openness": 0.7,
                    "conscientiousness": 0.8,
                    "extraversion": 0.6,
                    "agreeableness": 0.9,
                    "neuroticism": 0.2,
                },
                "communication_style": {
                    "tone": "friendly",
                    "verbosity": "medium",
                    "empathy": "high",
                },
            },
            "backstory": f"A helpful {name} assistant for testing.",
            "goals": {
                "primary": "Help with testing",
                "secondary": ["Be reliable", "Be fast"],
            },
        }

        char_data = data or default_data
        char_file = temp_config_dir / "characters" / f"{name}.yaml"

        with open(char_file, "w", encoding="utf-8") as f:
            yaml.dump(char_data, f, allow_unicode=True)

        return char_file

    return _create_character


@pytest.fixture
def test_characters(temp_config_dir: Path, create_test_character: callable) -> dict[str, Path]:
    """Create multiple test characters and return their paths."""
    characters = {}

    # Default character
    characters["default"] = create_test_character(
        "default",
        {
            "name": "Default Assistant",
            "version": "1.0.0",
            "relationship": "助手",
            "traits": {
                "personality": {
                    "openness": 0.7,
                    "conscientiousness": 0.8,
                    "extraversion": 0.6,
                    "agreeableness": 0.9,
                    "neuroticism": 0.2,
                },
                "communication_style": {
                    "tone": "professional",
                    "verbosity": "medium",
                    "empathy": "medium",
                },
            },
            "backstory": "The default assistant for testing purposes.",
            "goals": {
                "primary": "Provide helpful assistance",
                "secondary": ["Be accurate", "Be efficient"],
            },
        },
    )

    # Companion character
    characters["companion"] = create_test_character(
        "companion",
        {
            "name": "Friendly Companion",
            "version": "1.0.0",
            "relationship": "朋友",
            "traits": {
                "personality": {
                    "openness": 0.8,
                    "conscientiousness": 0.7,
                    "extraversion": 0.9,
                    "agreeableness": 0.95,
                    "neuroticism": 0.1,
                },
                "communication_style": {
                    "tone": "warm",
                    "verbosity": "high",
                    "empathy": "high",
                },
            },
            "backstory": "A friendly companion for testing persona switching.",
            "goals": {
                "primary": "Be a supportive friend",
                "secondary": ["Listen actively", "Show empathy"],
            },
        },
    )

    # Mentor character
    characters["mentor"] = create_test_character(
        "mentor",
        {
            "name": "Wise Mentor",
            "version": "1.0.0",
            "relationship": "导师",
            "traits": {
                "personality": {
                    "openness": 0.9,
                    "conscientiousness": 0.9,
                    "extraversion": 0.5,
                    "agreeableness": 0.85,
                    "neuroticism": 0.15,
                },
                "communication_style": {
                    "tone": "authoritative",
                    "verbosity": "medium",
                    "empathy": "medium",
                },
            },
            "backstory": "A wise mentor for testing different personas.",
            "goals": {
                "primary": "Guide and teach",
                "secondary": ["Share knowledge", "Encourage growth"],
            },
        },
    )

    return characters


# ============================================================================
# Service Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def session_repository(tmp_path: Path) -> AsyncGenerator[SessionRepository, None]:
    """Create a SessionRepository with a temporary database."""
    db_path = tmp_path / "test_sessions.db"
    repo = SessionRepository(db_path)
    await repo.connect()

    yield repo

    await repo.disconnect()


@pytest.fixture
def character_service(temp_config_dir: Path) -> CharacterService:
    """Create a CharacterService with temporary config."""
    return CharacterService(config_dir=temp_config_dir)


@pytest_asyncio.fixture
async def session_service(
    tmp_path: Path, session_repository: SessionRepository
) -> AsyncGenerator[SessionService, None]:
    """Create a SessionService with temporary database."""
    db_path = tmp_path / "test_sessions.db"
    service = SessionService(db_path, session_repo=session_repository)
    await service._ensure_connected()

    yield service

    await service.close()


@pytest.fixture
def mock_llm_client() -> Mock:
    """Create a mock LLM client that returns predictable responses."""
    mock = Mock(spec=LLMClient)

    async def mock_chat(*args, **kwargs) -> LLMResponse:
        """Return a mock LLM response."""
        return LLMResponse(
            content="This is a test response from the mock LLM.",
            model="gpt-4-test",
            usage={"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25},
        )

    mock.chat = AsyncMock(side_effect=mock_chat)

    async def mock_chat_stream(*args, **kwargs):
        """Yield mock streaming response chunks."""
        chunks = ["This ", "is ", "a ", "streaming ", "response."]
        for chunk in chunks:
            yield chunk

    mock.chat_stream = mock_chat_stream
    mock.provider = "openai"
    mock.model = "gpt-4-test"

    return mock


@pytest_asyncio.fixture
async def chat_service(
    temp_config_dir: Path,
    test_characters: dict[str, Path],
    mock_llm_client: Mock,
) -> AsyncGenerator[ChatService, None]:
    """Create a ChatService with real dependencies but mocked LLM."""
    character_service = CharacterService(config_dir=temp_config_dir)

    db_path = temp_config_dir / "test_chat.db"

    # Let ChatService create its own session_service internally to match actual usage
    service = ChatService(
        character_service=character_service,
        llm_client=mock_llm_client,
        db_path=db_path,
        default_persona="default",
    )

    yield service

    await service.close()


# ============================================================================
# Complex Integration Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def populated_session(
    session_repository: SessionRepository, test_characters: dict[str, Path]
) -> AsyncGenerator[tuple[str, list[dict]], None]:
    """Create a session with pre-populated messages."""
    from datetime import datetime

    from persona_agent.repositories.models import Session

    session_id = "test-populated-session"
    messages = [
        {
            "role": "system",
            "content": "persona:default",
            "timestamp": datetime.now().timestamp(),
        },
        {
            "role": "user",
            "content": "Hello, can you help me?",
            "timestamp": datetime.now().timestamp(),
        },
        {
            "role": "assistant",
            "content": "Of course! I'd be happy to help.",
            "timestamp": datetime.now().timestamp(),
        },
        {
            "role": "user",
            "content": "What's the weather like?",
            "timestamp": datetime.now().timestamp(),
        },
        {
            "role": "assistant",
            "content": "I don't have access to real-time weather data.",
            "timestamp": datetime.now().timestamp(),
        },
    ]

    session = Session(
        session_id=session_id,
        messages=messages,
        last_activity=datetime.now(),
    )

    await session_repository.create(session)

    yield session_id, messages


@pytest.fixture
def service_collection(temp_config_dir: Path, tmp_path: Path) -> Generator[dict, None, None]:
    """Create a collection of all services for complex integration tests."""
    from datetime import datetime

    collection = {
        "temp_config_dir": temp_config_dir,
        "db_path": tmp_path / "integration_test.db",
        "created_at": datetime.now(),
    }

    yield collection


# ============================================================================
# Helper Functions
# ============================================================================


@pytest.fixture
def assert_session_matches() -> callable:
    """Factory fixture providing a helper to assert session data matches expected."""

    def _assert_matches(session, expected_id: str, expected_message_count: int | None = None):
        """Assert that a session matches expected values."""
        assert session.session_id == expected_id
        if expected_message_count is not None:
            assert len(session.messages) == expected_message_count
        assert session.last_activity is not None

    return _assert_matches


@pytest.fixture
def create_message() -> callable:
    """Factory fixture to create message dictionaries."""
    from datetime import datetime

    def _create_message(role: str, content: str, timestamp: float | None = None) -> dict:
        """Create a message dictionary."""
        return {
            "role": role,
            "content": content,
            "timestamp": timestamp or datetime.now().timestamp(),
        }

    return _create_message
