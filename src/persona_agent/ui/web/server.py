"""Web UI server for Persona Agent."""

import json
import os
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from persona_agent.config.schemas.character import CharacterProfile
from persona_agent.core.hierarchical_memory import HierarchicalMemory
from persona_agent.services.character_service import CharacterService
from persona_agent.services.chat_service import (
    ChatInputFilteredError,
    ChatLLMError,
    ChatMessageError,
    ChatPersonaNotFoundError,
    ChatService,
    ChatSessionNotFoundError,
)
from persona_agent.services.session_service import SessionService
from persona_agent.ui.web.middleware import StructuredAccessLogMiddleware

_STATIC_DIR = Path(__file__).parent / "static"

_api_key: str | None = None


def verify_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    api_key: str | None = None,
) -> str:
    key = x_api_key or api_key
    if not _api_key:
        raise HTTPException(status_code=500, detail="API key not configured")
    if not key or key != _api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return key


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service


def get_session_service(request: Request) -> SessionService:
    return request.app.state.session_service


def get_character_service(request: Request) -> CharacterService:
    return request.app.state.character_service


def get_memory(request: Request) -> HierarchicalMemory:
    return request.app.state.memory


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _api_key
    app.state.chat_service = ChatService()
    app.state.session_service = SessionService()
    app.state.character_service = CharacterService()
    app.state.memory = HierarchicalMemory()

    env_key = os.environ.get("PERSONA_AGENT_API_KEY")
    if not env_key:
        raise RuntimeError("PERSONA_AGENT_API_KEY environment variable is required")
    _api_key = env_key

    yield
    await app.state.chat_service.close()
    await app.state.session_service.close()


limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Persona Agent Web UI", version="0.1.0", lifespan=lifespan)
app.add_middleware(StructuredAccessLogMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


# ============================================================================
# API Models
# ============================================================================


class CreateSessionRequest(BaseModel):
    persona_name: str | None = None


class ChatMessageRequest(BaseModel):
    message: str


class ChatMessageResponse(BaseModel):
    role: str
    content: str
    timestamp: float | None = None


class SessionSummary(BaseModel):
    session_id: str
    message_count: int
    last_activity: str


class SessionDetail(BaseModel):
    session_id: str
    persona_name: str
    message_count: int
    first_activity: str
    last_activity: str


class MemoryStatsResponse(BaseModel):
    working: dict[str, Any]
    episodic: dict[str, Any]
    semantic: dict[str, Any]


class DashboardStatsResponse(BaseModel):
    persona_count: int
    session_count_today: int
    memory_count: int
    skills_count: int


class CharacterCreateRequest(BaseModel):
    """Request model for creating a new character.

    All fields from CharacterProfile are available. Only 'name' is required.
    Other fields use sensible defaults from CharacterProfile.
    """

    name: str
    version: str = "1.0.0"
    relationship: str | None = None
    physical: dict[str, Any] | None = None
    height: str | None = None
    figure: str | None = None
    hair: str | None = None
    eyes: str | None = None
    attire: dict[str, str] | None = None
    traits: dict[str, Any] | None = None
    psychological_drivers: dict[str, Any] | None = None
    relationship_arcs: list[dict[str, Any]] = []
    backstory: str = ""
    core_memories: list[str] = []
    goals: dict[str, Any] | None = None
    knowledge_domains: list[str] = []
    limitations: list[str] = []
    interactive_hooks: list[str] = []
    mood_config: str | None = None
    linguistic_style: str | None = None


class CharacterUpdateRequest(BaseModel):
    """Request model for updating an existing character.

    All fields are optional since updates can be partial.
    Only provide the fields you want to change.
    """

    name: str | None = None
    version: str | None = None
    relationship: str | None = None
    physical: dict[str, Any] | None = None
    height: str | None = None
    figure: str | None = None
    hair: str | None = None
    eyes: str | None = None
    attire: dict[str, str] | None = None
    traits: dict[str, Any] | None = None
    psychological_drivers: dict[str, Any] | None = None
    relationship_arcs: list[dict[str, Any]] | None = None
    backstory: str | None = None
    core_memories: list[str] | None = None
    goals: dict[str, Any] | None = None
    knowledge_domains: list[str] | None = None
    limitations: list[str] | None = None
    interactive_hooks: list[str] | None = None
    mood_config: str | None = None
    linguistic_style: str | None = None


# ============================================================================
# Static Routes
# ============================================================================


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/stats")
@limiter.limit("30/minute")
async def get_stats(
    request: Request,
    api_key: str = Depends(verify_api_key),
    character_service: CharacterService = Depends(get_character_service),
    session_service: SessionService = Depends(get_session_service),
    memory: HierarchicalMemory = Depends(get_memory),
) -> DashboardStatsResponse:
    persona_count = len(character_service.list_characters())

    sessions = await session_service.list_sessions(limit=1000)
    today = date.today()
    session_count_today = 0
    for s in sessions:
        last_activity = s["last_activity"]
        if isinstance(last_activity, datetime):
            if last_activity.date() == today:
                session_count_today += 1
        elif isinstance(last_activity, str):
            try:
                if datetime.fromisoformat(last_activity).date() == today:
                    session_count_today += 1
            except Exception:
                pass

    memory_stats = memory.get_stats()
    memory_count = (
        memory_stats["working"].get("exchanges", 0)
        + memory_stats["episodic"].get("total_episodes", 0)
        + memory_stats["semantic"].get("entities", 0)
    )

    return DashboardStatsResponse(
        persona_count=persona_count,
        session_count_today=session_count_today,
        memory_count=memory_count,
        skills_count=0,
    )


# ============================================================================
# Session API
# ============================================================================


@app.get("/api/sessions")
@limiter.limit("30/minute")
async def list_sessions(
    request: Request,
    limit: int = 20,
    api_key: str = Depends(verify_api_key),
    session_service: SessionService = Depends(get_session_service),
) -> list[SessionSummary]:
    sessions = await session_service.list_sessions(limit=limit)
    return [
        SessionSummary(
            session_id=s["session_id"],
            message_count=s["message_count"],
            last_activity=s["last_activity"].isoformat()
            if hasattr(s["last_activity"], "isoformat")
            else str(s["last_activity"]),
        )
        for s in sessions
    ]


@app.post("/api/sessions")
@limiter.limit("30/minute")
async def create_session(
    request: Request,
    body: CreateSessionRequest | None = None,
    api_key: str = Depends(verify_api_key),
    chat_service: ChatService = Depends(get_chat_service),
) -> dict[str, str]:
    try:
        persona_name = body.persona_name if body else None
        session_id = await chat_service.create_new_session(persona_name=persona_name)
        return {"session_id": session_id}
    except ChatPersonaNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/sessions/{session_id}")
@limiter.limit("30/minute")
async def get_session(
    request: Request,
    session_id: str,
    api_key: str = Depends(verify_api_key),
    chat_service: ChatService = Depends(get_chat_service),
) -> SessionDetail:
    try:
        info = await chat_service.get_session_info(session_id)
        return SessionDetail(
            session_id=info["session_id"],
            persona_name=info["persona_name"],
            message_count=info["message_count"],
            first_activity=info["first_activity"].isoformat()
            if hasattr(info["first_activity"], "isoformat")
            else str(info["first_activity"]),
            last_activity=info["last_activity"].isoformat()
            if hasattr(info["last_activity"], "isoformat")
            else str(info["last_activity"]),
        )
    except ChatSessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.delete("/api/sessions/{session_id}")
@limiter.limit("30/minute")
async def delete_session(
    request: Request,
    session_id: str,
    api_key: str = Depends(verify_api_key),
    session_service: SessionService = Depends(get_session_service),
) -> dict[str, bool]:
    try:
        await session_service.delete_session(session_id)
        return {"deleted": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# Chat API
# ============================================================================


@app.post("/api/sessions/{session_id}/messages")
@limiter.limit("30/minute")
async def send_message(
    request: Request,
    session_id: str,
    body: ChatMessageRequest,
    api_key: str = Depends(verify_api_key),
    chat_service: ChatService = Depends(get_chat_service),
) -> dict[str, str]:
    try:
        response = await chat_service.send_message(session_id=session_id, message=body.message)
        return {"content": response}
    except ChatInputFilteredError as e:
        raise HTTPException(status_code=400, detail="Message contains disallowed content") from e
    except ChatSessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ChatPersonaNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


async def _stream_event_generator(session_id: str, message: str, chat_service: ChatService):
    """Generate SSE events for chat message streaming."""
    try:
        async for token in chat_service.send_message_stream(session_id=session_id, message=message):
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"
    except ChatInputFilteredError:
        yield f"data: {json.dumps({'error': 'Message contains disallowed content'})}\n\n"
    except (ChatSessionNotFoundError, ChatPersonaNotFoundError, ChatMessageError) as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
    except ChatLLMError as e:
        yield f"data: {json.dumps({'error': f'LLM error: {e}'})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': f'Unexpected error: {e}'})}\n\n"


@app.get("/api/sessions/{session_id}/messages/stream")
@limiter.limit("30/minute")
async def stream_message_get(
    request: Request,
    session_id: str,
    message: str = Query(..., description="Message to send"),
    api_key: str = Depends(verify_api_key),
    chat_service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    """Stream chat messages as Server-Sent Events (GET for EventSource compatibility).

    Uses EventSource protocol to stream tokens as they arrive from the LLM.
    Each event contains a JSON object with either a 'token' field containing
    the next text chunk, or a 'done' field indicating the stream is complete.
    """
    return StreamingResponse(
        _stream_event_generator(session_id, message, chat_service),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.post("/api/sessions/{session_id}/messages/stream")
@limiter.limit("30/minute")
async def stream_message_post(
    request: Request,
    session_id: str,
    body: ChatMessageRequest,
    api_key: str = Depends(verify_api_key),
    chat_service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    """Stream chat messages as Server-Sent Events (POST with request body).

    Uses EventSource protocol to stream tokens as they arrive from the LLM.
    Each event contains a JSON object with either a 'token' field containing
    the next text chunk, or a 'done' field indicating the stream is complete.
    """
    return StreamingResponse(
        _stream_event_generator(session_id, body.message, chat_service),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/sessions/{session_id}/history")
@limiter.limit("30/minute")
async def get_history(
    request: Request,
    session_id: str,
    api_key: str = Depends(verify_api_key),
    chat_service: ChatService = Depends(get_chat_service),
) -> list[ChatMessageResponse]:
    try:
        history = await chat_service.get_conversation_history(session_id, include_system=False)
        return [
            ChatMessageResponse(
                role=msg.get("role", "user"),
                content=msg.get("content", ""),
                timestamp=msg.get("timestamp"),
            )
            for msg in history
        ]
    except ChatSessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ============================================================================
# Character API
# ============================================================================


@app.get("/api/characters")
@limiter.limit("30/minute")
async def list_characters(
    request: Request,
    api_key: str = Depends(verify_api_key),
    character_service: CharacterService = Depends(get_character_service),
) -> list[str]:
    return character_service.list_characters()


@app.get("/api/characters/{name}")
@limiter.limit("30/minute")
async def get_character(
    request: Request,
    name: str,
    api_key: str = Depends(verify_api_key),
    character_service: CharacterService = Depends(get_character_service),
) -> dict[str, Any]:
    try:
        char = character_service.get_character(name)
        return char.model_dump()
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.post("/api/characters")
@limiter.limit("30/minute")
async def create_character(
    request: Request,
    body: CharacterCreateRequest,
    api_key: str = Depends(verify_api_key),
    character_service: CharacterService = Depends(get_character_service),
) -> dict[str, str]:
    try:
        profile = CharacterProfile(**body.model_dump())
        path = character_service.create_character(profile)
        return {"saved_to": str(path)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.put("/api/characters/{name}")
@limiter.limit("30/minute")
async def update_character(
    request: Request,
    name: str,
    body: CharacterUpdateRequest,
    api_key: str = Depends(verify_api_key),
    character_service: CharacterService = Depends(get_character_service),
) -> dict[str, str]:
    try:
        profile = CharacterProfile(**body.model_dump(exclude_none=True))
        path = character_service.update_character(name, profile)
        return {"saved_to": str(path)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ============================================================================
# Memory API
# ============================================================================


@app.get("/api/memory/stats")
@limiter.limit("30/minute")
async def memory_stats(
    request: Request,
    api_key: str = Depends(verify_api_key),
    memory: HierarchicalMemory = Depends(get_memory),
) -> MemoryStatsResponse:
    stats = memory.get_stats()
    return MemoryStatsResponse(
        working=stats["working"],
        episodic=stats["episodic"],
        semantic=stats["semantic"],
    )


@app.get("/api/memory/graph")
@limiter.limit("30/minute")
async def memory_graph(
    request: Request,
    api_key: str = Depends(verify_api_key),
    memory: HierarchicalMemory = Depends(get_memory),
) -> dict[str, list[dict[str, Any]]]:
    return memory.export_graph()


@app.get("/api/memory/retrieve")
@limiter.limit("30/minute")
async def memory_retrieve(
    request: Request,
    q: str,
    api_key: str = Depends(verify_api_key),
    memory: HierarchicalMemory = Depends(get_memory),
) -> dict[str, Any]:
    context = await memory.retrieve(q)
    return {
        "working_messages": [
            {"role": m.role, "content": m.content} for m in context.working_messages
        ],
        "episodic_memories": [
            {
                "id": m.id,
                "content": m.content,
                "importance": m.importance,
                "entities": m.entities,
            }
            for m in context.episodic_memories
        ],
        "semantic_facts": context.semantic_facts,
        "fusion_score": context.fusion_score,
    }


@app.get("/api/stats")
@limiter.limit("30/minute")
async def dashboard_stats(
    request: Request,
    api_key: str = Depends(verify_api_key),
    character_service: CharacterService = Depends(get_character_service),
    session_service: SessionService = Depends(get_session_service),
    memory: HierarchicalMemory = Depends(get_memory),
) -> DashboardStatsResponse:
    persona_count = len(character_service.list_characters())

    sessions = await session_service.list_sessions(limit=1000)
    today = date.today()
    session_count_today = 0
    for s in sessions:
        last_activity = s["last_activity"]
        if isinstance(last_activity, datetime):
            session_date = last_activity.date()
        elif isinstance(last_activity, str):
            session_date = datetime.fromisoformat(last_activity).date()
        else:
            continue
        if session_date == today:
            session_count_today += 1

    mem_stats = memory.get_stats()
    memory_count = (
        mem_stats["working"].get("exchanges", 0)
        + mem_stats["episodic"].get("total_episodes", 0)
        + mem_stats["semantic"].get("entities", 0)
        + mem_stats["semantic"].get("facts", 0)
        + mem_stats["semantic"].get("relations", 0)
    )

    skills_count = 0

    return DashboardStatsResponse(
        persona_count=persona_count,
        session_count_today=session_count_today,
        memory_count=memory_count,
        skills_count=skills_count,
    )


# Rebuild Pydantic models to resolve forward references from `from __future__ import annotations`
CreateSessionRequest.model_rebuild()
ChatMessageRequest.model_rebuild()
ChatMessageResponse.model_rebuild()
SessionSummary.model_rebuild()
SessionDetail.model_rebuild()
MemoryStatsResponse.model_rebuild()
DashboardStatsResponse.model_rebuild()
CharacterCreateRequest.model_rebuild()
CharacterUpdateRequest.model_rebuild()
