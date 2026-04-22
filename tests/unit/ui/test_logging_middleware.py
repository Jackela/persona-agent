import json
from unittest.mock import AsyncMock, Mock

import pytest

from persona_agent.ui.web.middleware.logging import StructuredAccessLogMiddleware


@pytest.mark.asyncio
async def test_middleware_calls_next_app_and_logs_json():
    async def _app(scope, receive, send):
        await send({"type": "http.response.start", "status": 201})

    mock_app = AsyncMock(side_effect=_app)
    mock_logger = Mock()
    middleware = StructuredAccessLogMiddleware(mock_app, logger=mock_logger)

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/test",
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 12345),
    }
    receive = AsyncMock()
    send = AsyncMock()

    await middleware(scope, receive, send)

    mock_app.assert_awaited_once()
    assert mock_logger.info.called

    log_call = mock_logger.info.call_args[0][0]
    log_data = json.loads(log_call)

    assert log_data["method"] == "GET"
    assert log_data["path"] == "/api/test"
    assert log_data["status_code"] == 201
    assert "latency_ms" in log_data
    assert isinstance(log_data["latency_ms"], float)
    assert log_data["client_ip"] == "127.0.0.1"
    assert "trace_id" in log_data
    assert len(log_data["trace_id"]) == 32


@pytest.mark.asyncio
async def test_middleware_does_not_log_api_key_query_param():
    async def _app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200})

    mock_app = AsyncMock(side_effect=_app)
    mock_logger = Mock()
    middleware = StructuredAccessLogMiddleware(mock_app, logger=mock_logger)

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/sessions",
        "headers": [],
        "query_string": b"api_key=secret123&limit=10",
        "client": ("127.0.0.1", 12345),
    }
    receive = AsyncMock()
    send = AsyncMock()

    await middleware(scope, receive, send)

    log_call = mock_logger.info.call_args[0][0]
    log_data = json.loads(log_call)

    assert "secret123" not in log_call
    assert log_data["path"] == "/api/sessions"


@pytest.mark.asyncio
async def test_middleware_skips_non_http_scope():
    mock_app = AsyncMock()
    mock_logger = Mock()
    middleware = StructuredAccessLogMiddleware(mock_app, logger=mock_logger)

    scope = {"type": "websocket", "path": "/ws"}
    receive = AsyncMock()
    send = AsyncMock()

    await middleware(scope, receive, send)

    mock_app.assert_awaited_once_with(scope, receive, send)
    mock_logger.info.assert_not_called()
