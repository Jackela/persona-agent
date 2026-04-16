"""Structured access logging middleware."""

import json
import logging
import time
import uuid

from starlette.requests import Request


class StructuredAccessLogMiddleware:
    """ASGI middleware that logs every HTTP request as a structured JSON line."""

    def __init__(self, app, logger: logging.Logger | None = None):
        self.app = app
        self.logger = logger or logging.getLogger("persona_agent.access")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        trace_id = uuid.uuid4().hex
        request.state.trace_id = trace_id

        start = time.perf_counter()
        status_code = 200

        async def wrapped_send(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)
            await send(message)

        await self.app(scope, receive, wrapped_send)

        latency_ms = round((time.perf_counter() - start) * 1000, 3)
        self.logger.info(
            json.dumps(
                {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "latency_ms": latency_ms,
                    "client_ip": request.client.host if request.client else None,
                    "trace_id": trace_id,
                }
            )
        )
