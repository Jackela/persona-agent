"""Web UI server for Persona Agent."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from persona_agent.config.schemas.character import CharacterProfile
from persona_agent.core.hierarchical_memory import HierarchicalMemory
from persona_agent.services.character_service import CharacterService
from persona_agent.services.chat_service import (
    ChatPersonaNotFoundError,
    ChatService,
    ChatSessionNotFoundError,
)
from persona_agent.services.session_service import SessionService

_STATIC_DIR = Path(__file__).parent / "static"

_chat_service: ChatService | None = None
_session_service: SessionService | None = None
_character_service: CharacterService | None = None
_memory: HierarchicalMemory | None = None


def _get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _session_service, _character_service, _memory
    _session_service = SessionService()
    _character_service = CharacterService()
    _memory = HierarchicalMemory()
    yield
    if _chat_service is not None:
        await _chat_service.close()
    await _session_service.close()


app = FastAPI(title="Persona Agent Web UI", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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


# ============================================================================
# Static Routes
# ============================================================================


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ============================================================================
# Session API
# ============================================================================


@app.get("/api/sessions")
async def list_sessions(limit: int = 20) -> list[SessionSummary]:
    sessions = await _session_service.list_sessions(limit=limit)
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
async def create_session(body: CreateSessionRequest) -> dict[str, str]:
    try:
        session_id = await _get_chat_service().create_new_session(persona_name=body.persona_name)
        return {"session_id": session_id}
    except ChatPersonaNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str) -> SessionDetail:
    try:
        info = await _get_chat_service().get_session_info(session_id)
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
async def delete_session(session_id: str) -> dict[str, bool]:
    try:
        await _session_service.delete_session(session_id)
        return {"deleted": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# Chat API
# ============================================================================


@app.post("/api/sessions/{session_id}/messages")
async def send_message(session_id: str, body: ChatMessageRequest) -> dict[str, str]:
    try:
        response = await _get_chat_service().send_message(
            session_id=session_id, message=body.message
        )
        return {"content": response}
    except ChatSessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ChatPersonaNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/sessions/{session_id}/history")
async def get_history(session_id: str) -> list[ChatMessageResponse]:
    try:
        history = await _get_chat_service().get_conversation_history(
            session_id, include_system=False
        )
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
async def list_characters() -> list[str]:
    return _character_service.list_characters()


@app.get("/api/characters/{name}")
async def get_character(name: str) -> dict[str, Any]:
    try:
        char = _character_service.get_character(name)
        return char.model_dump()
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.post("/api/characters")
async def create_character(body: dict[str, Any]) -> dict[str, str]:
    try:
        profile = CharacterProfile(**body)
        path = _character_service.create_character(profile)
        return {"saved_to": str(path)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.put("/api/characters/{name}")
async def update_character(name: str, body: dict[str, Any]) -> dict[str, str]:
    try:
        profile = CharacterProfile(**body)
        path = _character_service.update_character(name, profile)
        return {"saved_to": str(path)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ============================================================================
# Memory API
# ============================================================================


@app.get("/api/memory/stats")
async def memory_stats() -> MemoryStatsResponse:
    stats = _memory.get_stats()
    return MemoryStatsResponse(
        working=stats["working"],
        episodic=stats["episodic"],
        semantic=stats["semantic"],
    )


@app.get("/api/memory/graph")
async def memory_graph() -> dict[str, list[dict[str, Any]]]:
    return _memory.export_graph()


@app.get("/api/memory/retrieve")
async def memory_retrieve(q: str) -> dict[str, Any]:
    context = await _memory.retrieve(q)
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
