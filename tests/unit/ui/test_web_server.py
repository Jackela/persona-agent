import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from fastapi.testclient import TestClient


def _fake_limiter_limit(rate: str):
    def decorator(func):
        return func

    return decorator


class _FakeLimiter:
    def __init__(self, *args, **kwargs):
        pass

    limit = staticmethod(_fake_limiter_limit)


slowapi_mock = MagicMock()
slowapi_mock.Limiter = _FakeLimiter
slowapi_mock._rate_limit_exceeded_handler = MagicMock()
slowapi_mock.errors.RateLimitExceeded = Exception
slowapi_mock.util.get_remote_address = MagicMock()
sys.modules["slowapi"] = slowapi_mock
sys.modules["slowapi.errors"] = slowapi_mock.errors
sys.modules["slowapi.util"] = slowapi_mock.util

from persona_agent.ui.web import server as web_server

import importlib

importlib.reload(web_server)


@pytest.fixture
def test_api_key():
    return "test-api-key-123"


@pytest.fixture
def client(test_api_key):
    mock_session = Mock()
    mock_session.list_sessions = AsyncMock(return_value=[])
    mock_session.delete_session = AsyncMock(return_value=None)

    mock_char = Mock()
    mock_char.list_characters = Mock(return_value=[])
    mock_char.get_character = Mock(
        return_value=Mock(model_dump=Mock(return_value={"name": "test"}))
    )
    mock_char.create_character = Mock(return_value=Mock())
    mock_char.update_character = Mock(return_value=Mock())

    mock_mem = Mock()
    mock_mem.get_stats = Mock(return_value={"working": {}, "episodic": {}, "semantic": {}})
    mock_mem.export_graph = Mock(return_value={"nodes": [], "edges": []})
    mock_mem.retrieve = AsyncMock(
        return_value=Mock(
            working_messages=[], episodic_memories=[], semantic_facts=[], fusion_score=0.0
        )
    )

    mock_chat = Mock()
    mock_chat.create_new_session = AsyncMock(return_value="test-session-id")
    mock_chat.get_session_info = AsyncMock(
        return_value={
            "session_id": "test",
            "persona_name": "default",
            "message_count": 0,
            "first_activity": datetime.now(),
            "last_activity": datetime.now(),
        }
    )
    mock_chat.send_message = AsyncMock(return_value="hello")
    mock_chat.get_conversation_history = AsyncMock(return_value=[])
    mock_chat.send_message_stream = Mock(return_value=_async_iter([]))
    mock_chat.close = AsyncMock()

    web_server.app.dependency_overrides = {
        web_server.get_chat_service: lambda: mock_chat,
        web_server.get_session_service: lambda: mock_session,
        web_server.get_character_service: lambda: mock_char,
        web_server.get_memory: lambda: mock_mem,
    }

    original_key = web_server._api_key
    web_server._api_key = test_api_key
    yield TestClient(web_server.app)
    web_server._api_key = original_key
    web_server.app.dependency_overrides.clear()


class TestStaticRoutesUnauthenticated:
    def test_root_route_no_auth(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_health_route_no_auth(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_static_files_no_auth(self, client):
        response = client.get("/static/app.js")
        assert response.status_code in (200, 404)


class TestApiKeyAuthentication:
    def test_api_route_without_key_returns_401(self, client):
        response = client.get("/api/sessions")
        assert response.status_code == 401
        assert (
            "Invalid API key" in response.json()["detail"]
            or "API key not configured" in response.json()["detail"]
        )

    def test_api_route_with_wrong_key_returns_401(self, client):
        response = client.get("/api/sessions", headers={"X-API-Key": "wrong-key"})
        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]

    def test_api_route_with_valid_key_succeeds(self, client):
        response = client.get("/api/sessions", headers={"X-API-Key": "test-api-key-123"})
        assert response.status_code == 200

    def test_api_sessions_post_requires_auth(self, client):
        response = client.post("/api/sessions", json={"persona_name": "default"})
        assert response.status_code == 401

    def test_api_characters_get_requires_auth(self, client):
        response = client.get("/api/characters")
        assert response.status_code == 401

    def test_api_memory_graph_requires_auth(self, client):
        response = client.get("/api/memory/graph")
        assert response.status_code == 401


class TestCharacterEndpoints:
    def test_create_character_with_pydantic_model(self, client):
        response = client.post(
            "/api/characters",
            headers={"X-API-Key": "test-api-key-123"},
            json={
                "name": "test-char",
                "version": "1.0.0",
                "backstory": "A test character.",
                "goals": {"primary": "test goal"},
            },
        )
        assert response.status_code == 200
        assert "saved_to" in response.json()

    def test_update_character_with_pydantic_model(self, client):
        response = client.put(
            "/api/characters/test-char",
            headers={"X-API-Key": "test-api-key-123"},
            json={
                "name": "test-char",
                "backstory": "Updated backstory.",
            },
        )
        assert response.status_code == 200
        assert "saved_to" in response.json()


class TestApiKeyDefaultValue:
    def test_default_api_key_is_dev(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(web_server, "_api_key", None)
            env_key = web_server.os.environ.get("PERSONA_AGENT_API_KEY")
            if env_key is None:
                assert web_server._api_key is None
            else:
                assert web_server._api_key == env_key

    def test_verify_api_key_rejects_invalid(self, test_api_key):
        web_server._api_key = test_api_key
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            web_server.verify_api_key("wrong-key")
        assert exc_info.value.status_code == 401
        web_server._api_key = None

    def test_verify_api_key_accepts_valid(self, test_api_key):
        web_server._api_key = test_api_key
        result = web_server.verify_api_key(test_api_key)
        assert result == test_api_key
        web_server._api_key = None


class TestStatsEndpoint:
    def test_api_stats_requires_auth(self, client):
        response = client.get("/api/stats")
        assert response.status_code == 401

    def test_api_stats_returns_expected_fields(self, client):
        response = client.get("/api/stats", headers={"X-API-Key": "test-api-key-123"})
        assert response.status_code == 200
        data = response.json()
        assert "persona_count" in data
        assert "session_count_today" in data
        assert "memory_count" in data
        assert "skills_count" in data
        assert data["skills_count"] == 0


class TestSSEEndpoint:
    def test_stream_requires_auth(self, client):
        response = client.get("/api/sessions/test-session/messages/stream?message=hello")
        assert response.status_code == 401

    def test_stream_with_header_auth(self, client):
        mock_chat = web_server.app.dependency_overrides[web_server.get_chat_service]()
        mock_chat.send_message_stream = Mock(return_value=_async_iter(["Hello", " world"]))
        response = client.get(
            "/api/sessions/test-session/messages/stream?message=hello",
            headers={"X-API-Key": "test-api-key-123"},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_stream_with_query_auth(self, client):
        mock_chat = web_server.app.dependency_overrides[web_server.get_chat_service]()
        mock_chat.send_message_stream = Mock(return_value=_async_iter(["Hello", " world"]))
        response = client.get(
            "/api/sessions/test-session/messages/stream?message=hello&api_key=test-api-key-123",
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_stream_outputs_sse_events(self, client):
        mock_chat = web_server.app.dependency_overrides[web_server.get_chat_service]()
        mock_chat.send_message_stream = Mock(return_value=_async_iter(["Hello", " world"]))
        response = client.get(
            "/api/sessions/test-session/messages/stream?message=hello",
            headers={"X-API-Key": "test-api-key-123"},
        )
        body = response.text
        assert 'data: {"token": "Hello"}' in body
        assert 'data: {"token": " world"}' in body
        assert 'data: {"done": true}' in body

    def test_stream_error_in_event(self, client):
        mock_chat = web_server.app.dependency_overrides[web_server.get_chat_service]()
        from persona_agent.services.chat_service import ChatSessionNotFoundError

        mock_chat.send_message_stream = Mock(side_effect=ChatSessionNotFoundError("bad-session"))
        response = client.get(
            "/api/sessions/bad-session/messages/stream?message=hello",
            headers={"X-API-Key": "test-api-key-123"},
        )
        body = response.text
        assert '"error"' in body


def _async_iter(items):
    async def _gen():
        for item in items:
            yield item

    return _gen()
