"""Integration tests for service interactions.

Tests direct interactions between services without going through the full
chat workflow, verifying service boundaries and data consistency.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock

from persona_agent.config.schemas.character import CharacterProfile
from persona_agent.repositories.models import Session
from persona_agent.services.character_service import (
    CharacterService,
    CharacterNotFoundError,
)
from persona_agent.services.chat_service import ChatService, ChatSessionNotFoundError
from persona_agent.services.session_service import (
    SessionService,
    SessionNotFoundError,
)
from persona_agent.repositories import SessionRepository
from persona_agent.utils.llm_client import LLMResponse


@pytest.mark.asyncio
class TestCharacterServiceWithChatService:
    """Test CharacterService integration with ChatService."""

    async def test_chat_service_uses_character_service_for_validation(
        self, chat_service, character_service
    ):
        """Test that ChatService uses CharacterService to validate personas."""
        characters = character_service.list_characters()
        assert "default" in characters
        assert "companion" in characters
        assert "mentor" in characters

    async def test_chat_service_gets_character_via_character_service(self, chat_service):
        """Test that ChatService retrieves character profiles correctly."""
        session_id = await chat_service.create_new_session(persona_name="companion")
        info = await chat_service.get_session_info(session_id)
        assert info["persona_name"] == "companion"

    async def test_character_service_provides_profile_to_chat_service(self, chat_service):
        """Test that CharacterService provides full profiles to ChatService."""
        session_id = await chat_service.create_new_session(persona_name="mentor")
        response = await chat_service.send_message(session_id, "Test")
        assert response is not None

    async def test_chat_service_reflects_character_service_changes(
        self, temp_config_dir, test_characters
    ):
        """Test that changes in CharacterService are reflected in ChatService."""
        import yaml

        char_service1 = CharacterService(config_dir=temp_config_dir)

        new_char_path = temp_config_dir / "characters" / "dynamic.yaml"
        new_char_data = {
            "name": "Dynamic Character",
            "version": "1.0.0",
            "relationship": "助手",
            "traits": {
                "personality": {
                    "openness": 0.5,
                    "conscientiousness": 0.5,
                    "extraversion": 0.5,
                    "agreeableness": 0.5,
                    "neuroticism": 0.5,
                },
                "communication_style": {
                    "tone": "neutral",
                    "verbosity": "medium",
                    "empathy": "medium",
                },
            },
            "backstory": "A dynamic test character.",
            "goals": {"primary": "Test", "secondary": []},
        }
        with open(new_char_path, "w") as f:
            yaml.dump(new_char_data, f)

        char_service2 = CharacterService(config_dir=temp_config_dir)
        assert "dynamic" in char_service2.list_characters()

        mock_llm = Mock()

        async def mock_chat(*args, **kwargs):
            return LLMResponse(content="OK", model="test", usage={})

        mock_llm.chat = mock_chat

        chat_service = ChatService(
            character_service=char_service2,
            llm_client=mock_llm,
            db_path=temp_config_dir / "test.db",
        )

        session_id = await chat_service.create_new_session(persona_name="dynamic")
        info = await chat_service.get_session_info(session_id)
        assert info["persona_name"] == "dynamic"

        await chat_service.close()


@pytest.mark.asyncio
class TestSessionServiceWithRepository:
    """Test SessionService integration with SessionRepository."""

    async def test_session_service_uses_repository_for_create(
        self, session_service, session_repository
    ):
        """Test that SessionService uses repository for creating sessions."""
        session = Session(
            session_id="test-session",
            messages=[
                {"role": "user", "content": "Hello", "timestamp": datetime.now().timestamp()}
            ],
            last_activity=datetime.now(),
        )
        await session_repository.create(session)

        retrieved = await session_repository.get_by_id("test-session")
        assert retrieved is not None
        assert retrieved.session_id == "test-session"

    async def test_session_service_reflects_repository_changes(
        self, session_service, session_repository
    ):
        """Test that changes made via repository are visible through service."""
        session = Session(
            session_id="repo-session",
            messages=[],
            last_activity=datetime.now(),
        )
        await session_repository.create(session)

        assert await session_service.session_exists("repo-session")

        sessions = await session_service.list_sessions()
        session_ids = [s["session_id"] for s in sessions]
        assert "repo-session" in session_ids

    async def test_session_service_delete_propagates_to_repository(
        self, session_service, session_repository
    ):
        """Test that delete via service removes from repository."""
        session = Session(
            session_id="delete-test",
            messages=[],
            last_activity=datetime.now(),
        )
        await session_repository.create(session)

        assert await session_repository.exists("delete-test")

        result = await session_service.delete_session("delete-test")
        assert result is True

        assert not await session_repository.exists("delete-test")

    async def test_session_service_list_reflects_repository_state(
        self, session_service, session_repository
    ):
        """Test that service list reflects actual repository state."""
        for i in range(5):
            session = Session(
                session_id=f"list-test-{i}",
                messages=[
                    {
                        "role": "user",
                        "content": f"Message {i}",
                        "timestamp": datetime.now().timestamp(),
                    }
                ],
                last_activity=datetime.now(),
            )
            await session_repository.create(session)

        sessions = await session_service.list_sessions(limit=10)
        session_ids = {s["session_id"] for s in sessions}

        for i in range(5):
            assert f"list-test-{i}" in session_ids

    async def test_session_service_gets_full_session_from_repository(
        self, session_service, session_repository
    ):
        """Test that service retrieves complete session data from repository."""
        session = Session(
            session_id="full-session",
            messages=[
                {"role": "user", "content": "Message 1", "timestamp": datetime.now().timestamp()},
                {
                    "role": "assistant",
                    "content": "Response 1",
                    "timestamp": datetime.now().timestamp(),
                },
                {"role": "user", "content": "Message 2", "timestamp": datetime.now().timestamp()},
            ],
            last_activity=datetime.now(),
        )
        await session_repository.create(session)

        info = await session_service.get_session_info("full-session")

        assert info["session_id"] == "full-session"
        assert info["message_count"] == 3
        assert len(info["recent_messages"]) == 3

    async def test_repository_isolation_between_tests(self, tmp_path):
        """Test that each test gets isolated repository instance."""
        db_path1 = tmp_path / "test1.db"
        db_path2 = tmp_path / "test2.db"

        repo1 = SessionRepository(db_path1)
        repo2 = SessionRepository(db_path2)

        await repo1.connect()
        await repo2.connect()

        session1 = Session(
            session_id="test",
            messages=[],
            last_activity=datetime.now(),
        )
        await repo1.create(session1)

        assert not await repo2.exists("test")

        await repo1.disconnect()
        await repo2.disconnect()


@pytest.mark.asyncio
class TestChatServiceWithSessionService:
    """Test ChatService integration with SessionService."""

    async def test_chat_service_uses_session_service_for_session_management(
        self, temp_config_dir, test_characters
    ):
        """Test that ChatService uses SessionService for session operations."""
        db_path = temp_config_dir / "integration.db"
        char_service = CharacterService(config_dir=temp_config_dir)

        mock_llm = Mock()

        async def mock_chat(*args, **kwargs):
            return LLMResponse(content="OK", model="test", usage={})

        mock_llm.chat = mock_chat

        repo = SessionRepository(db_path)
        await repo.connect()
        session_service = SessionService(db_path, session_repo=repo)

        chat_service = ChatService(
            character_service=char_service,
            session_service=session_service,
            llm_client=mock_llm,
            db_path=db_path,
        )

        session_id = await chat_service.create_new_session(persona_name="default")

        assert await session_service.session_exists(session_id)

        session_info = await session_service.get_session_info(session_id)
        assert session_info["session_id"] == session_id

        await chat_service.close()

    async def test_chat_service_creates_sessions_accessible_via_session_service(
        self, temp_config_dir, test_characters
    ):
        """Test that sessions created by ChatService are accessible via SessionService."""
        db_path = temp_config_dir / "integration2.db"
        char_service = CharacterService(config_dir=temp_config_dir)

        mock_llm = Mock()

        async def mock_chat(*args, **kwargs):
            return LLMResponse(content="OK", model="test", usage={})

        mock_llm.chat = mock_chat

        repo = SessionRepository(db_path)
        await repo.connect()
        session_service = SessionService(db_path, session_repo=repo)

        chat_service = ChatService(
            character_service=char_service,
            session_service=session_service,
            llm_client=mock_llm,
            db_path=db_path,
        )

        session_ids = []
        for _ in range(3):
            sid = await chat_service.create_new_session(persona_name="default")
            session_ids.append(sid)

        sessions = await session_service.list_sessions(limit=10)
        listed_ids = {s["session_id"] for s in sessions}

        for sid in session_ids:
            assert sid in listed_ids

        await chat_service.close()

    async def test_chat_service_updates_persist_through_session_service(
        self, temp_config_dir, test_characters
    ):
        """Test that message updates persist and are accessible via SessionService."""
        db_path = temp_config_dir / "integration3.db"
        char_service = CharacterService(config_dir=temp_config_dir)

        mock_llm = Mock()

        async def mock_chat(*args, **kwargs):
            return LLMResponse(content="OK", model="test", usage={})

        mock_llm.chat = mock_chat

        repo = SessionRepository(db_path)
        await repo.connect()
        session_service = SessionService(db_path, session_repo=repo)

        chat_service = ChatService(
            character_service=char_service,
            session_service=session_service,
            llm_client=mock_llm,
            db_path=db_path,
        )

        session_id = await chat_service.create_new_session(persona_name="default")
        await chat_service.send_message(session_id, "Hello")

        info = await session_service.get_session_info(session_id)
        assert info["message_count"] == 3

        await chat_service.close()

    async def test_session_service_deletes_propagate_to_chat_service(
        self, temp_config_dir, test_characters
    ):
        """Test that deletions via SessionService affect ChatService."""
        db_path = temp_config_dir / "integration4.db"
        char_service = CharacterService(config_dir=temp_config_dir)

        mock_llm = Mock()

        async def mock_chat(*args, **kwargs):
            return LLMResponse(content="OK", model="test", usage={})

        mock_llm.chat = mock_chat

        repo = SessionRepository(db_path)
        await repo.connect()
        session_service = SessionService(db_path, session_repo=repo)

        chat_service = ChatService(
            character_service=char_service,
            session_service=session_service,
            llm_client=mock_llm,
            db_path=db_path,
        )

        session_id = await chat_service.create_new_session(persona_name="default")

        info = await chat_service.get_session_info(session_id)
        assert info["session_id"] == session_id

        result = await session_service.delete_session(session_id)
        assert result is True

        with pytest.raises(ChatSessionNotFoundError):
            await chat_service.get_session_info(session_id)

        await chat_service.close()

    async def test_concurrent_operations_on_same_session(self, temp_config_dir, test_characters):
        """Test that concurrent operations work correctly."""
        db_path = temp_config_dir / "integration5.db"
        char_service = CharacterService(config_dir=temp_config_dir)

        mock_llm = Mock()

        async def mock_chat(*args, **kwargs):
            return LLMResponse(content="OK", model="test", usage={})

        mock_llm.chat = mock_chat

        repo = SessionRepository(db_path)
        await repo.connect()
        session_service = SessionService(db_path, session_repo=repo)

        chat_service = ChatService(
            character_service=char_service,
            session_service=session_service,
            llm_client=mock_llm,
            db_path=db_path,
        )

        session_id = await chat_service.create_new_session(persona_name="default")

        for i in range(5):
            await chat_service.send_message(session_id, f"Message {i}")

        info = await session_service.get_session_info(session_id)
        assert info["message_count"] == 11

        await chat_service.close()

    async def test_chat_service_and_session_service_share_repository(self, temp_config_dir):
        """Test that both services share the same repository instance."""
        db_path = temp_config_dir / "integration6.db"
        char_service = CharacterService(config_dir=temp_config_dir)

        mock_llm = Mock()

        async def mock_chat(*args, **kwargs):
            return LLMResponse(content="OK", model="test", usage={})

        mock_llm.chat = mock_chat

        repo = SessionRepository(db_path)
        await repo.connect()
        session_service = SessionService(db_path, session_repo=repo)

        chat_service = ChatService(
            character_service=char_service,
            session_service=session_service,
            llm_client=mock_llm,
            db_path=db_path,
        )

        session = Session(
            session_id="shared-test",
            messages=[
                {"role": "user", "content": "Direct", "timestamp": datetime.now().timestamp()}
            ],
            last_activity=datetime.now(),
        )
        await repo.create(session)

        assert await session_service.session_exists("shared-test")

        history = await chat_service.get_conversation_history("shared-test")
        assert len(history) == 1
        assert history[0]["content"] == "Direct"

        await chat_service.close()


@pytest.mark.asyncio
class TestServiceInitializationPatterns:
    """Test different service initialization patterns."""

    async def test_services_with_shared_repository(self, temp_config_dir, test_characters):
        """Test that services can share a repository instance."""
        db_path = temp_config_dir / "shared.db"

        repo = SessionRepository(db_path)
        await repo.connect()

        char_service = CharacterService(config_dir=temp_config_dir)
        session_service = SessionService(db_path, session_repo=repo)

        mock_llm = Mock()

        async def mock_chat(*args, **kwargs):
            return LLMResponse(content="OK", model="test", usage={})

        mock_llm.chat = mock_chat

        chat_service = ChatService(
            character_service=char_service,
            session_service=session_service,
            llm_client=mock_llm,
            db_path=db_path,
        )

        session_id = await chat_service.create_new_session(persona_name="default")

        assert await session_service.session_exists(session_id)

        await chat_service.close()

    async def test_services_with_independent_repositories(self, temp_config_dir, test_characters):
        """Test that services can have independent repositories."""
        db_path1 = temp_config_dir / "service1.db"
        db_path2 = temp_config_dir / "service2.db"

        char_service = CharacterService(config_dir=temp_config_dir)

        mock_llm = Mock()

        async def mock_chat(*args, **kwargs):
            return LLMResponse(content="OK", model="test", usage={})

        mock_llm.chat = mock_chat

        chat_service1 = ChatService(
            character_service=char_service,
            llm_client=mock_llm,
            db_path=db_path1,
        )

        chat_service2 = ChatService(
            character_service=char_service,
            llm_client=mock_llm,
            db_path=db_path2,
        )

        session1 = await chat_service1.create_new_session(persona_name="default")
        session2 = await chat_service2.create_new_session(persona_name="companion")

        with pytest.raises(ChatSessionNotFoundError):
            await chat_service2.get_session_info(session1)

        with pytest.raises(ChatSessionNotFoundError):
            await chat_service1.get_session_info(session2)

        await chat_service1.close()
        await chat_service2.close()

    async def test_service_lifecycle_management(self, temp_config_dir, test_characters):
        """Test proper service lifecycle management with async context managers."""
        db_path = temp_config_dir / "lifecycle.db"
        char_service = CharacterService(config_dir=temp_config_dir)

        mock_llm = Mock()

        async def mock_chat(*args, **kwargs):
            return LLMResponse(content="OK", model="test", usage={})

        mock_llm.chat = mock_chat

        async with ChatService(
            character_service=char_service,
            llm_client=mock_llm,
            db_path=db_path,
        ) as chat_service:
            session_id = await chat_service.create_new_session(persona_name="default")
            info = await chat_service.get_session_info(session_id)
            assert info["session_id"] == session_id
