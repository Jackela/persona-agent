"""Web UI server for Persona Agent."""

import json
import os
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
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
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse

app.add_exception_handler(
    RateLimitExceeded,
    lambda req, exc: _rate_limit_exceeded_handler(req, exc),  # type: ignore[arg-type]
)
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
    """Request model for creating a new chat session."""

    persona_name: str | None = Field(
        default=None,
        description="Name of the persona to use for this session. Defaults to the system default if omitted.",
        examples=["companion"],
    )


class ChatMessageRequest(BaseModel):
    """Request model for sending a chat message."""

    message: str = Field(
        description="The text message to send to the persona.",
        examples=["Hello, how are you today?"],
    )


class ChatMessageResponse(BaseModel):
    """Response model representing a single chat message."""

    role: str = Field(
        description="Role of the message sender, e.g. 'user', 'assistant', or 'system'.",
        examples=["assistant"],
    )
    content: str = Field(
        description="Text content of the message.",
        examples=["I'm doing well, thank you for asking!"],
    )
    timestamp: float | None = Field(
        default=None,
        description="Unix timestamp of when the message was created.",
        examples=[1713840000.0],
    )


class SessionSummary(BaseModel):
    """Summary representation of a chat session."""

    session_id: str = Field(
        description="Unique identifier for the session.",
        examples=["sess_abc123"],
    )
    message_count: int = Field(
        description="Total number of messages in the session.",
        examples=[42],
    )
    last_activity: str = Field(
        description="ISO-formatted timestamp of the last activity in the session.",
        examples=["2024-04-23T10:30:00"],
    )


class SessionDetail(BaseModel):
    """Detailed representation of a chat session."""

    session_id: str = Field(
        description="Unique identifier for the session.",
        examples=["sess_abc123"],
    )
    persona_name: str = Field(
        description="Name of the persona assigned to this session.",
        examples=["companion"],
    )
    message_count: int = Field(
        description="Total number of messages in the session.",
        examples=[42],
    )
    first_activity: str = Field(
        description="ISO-formatted timestamp of the first message in the session.",
        examples=["2024-04-23T08:00:00"],
    )
    last_activity: str = Field(
        description="ISO-formatted timestamp of the last activity in the session.",
        examples=["2024-04-23T10:30:00"],
    )


class MemoryStatsResponse(BaseModel):
    """Response model containing hierarchical memory statistics."""

    working: dict[str, Any] = Field(
        description="Statistics for working memory (recent exchanges).",
        examples=[{"exchanges": 10, "max_size": 20}],
    )
    episodic: dict[str, Any] = Field(
        description="Statistics for episodic memory (conversation episodes).",
        examples=[{"total_episodes": 5}],
    )
    semantic: dict[str, Any] = Field(
        description="Statistics for semantic memory (facts and entities).",
        examples=[{"entities": 3, "facts": 12}],
    )


class DashboardStatsResponse(BaseModel):
    """Response model for dashboard statistics."""

    persona_count: int = Field(
        description="Number of configured personas/characters.",
        examples=[5],
    )
    session_count_today: int = Field(
        description="Number of chat sessions created or active today.",
        examples=[12],
    )
    memory_count: int = Field(
        description="Total number of memory entries across all tiers.",
        examples=[150],
    )
    skills_count: int = Field(
        description="Number of registered skills.",
        examples=[3],
    )


class CharacterCreateRequest(BaseModel):
    """Request model for creating a new character.

    All fields from CharacterProfile are available. Only 'name' is required.
    Other fields use sensible defaults from CharacterProfile.
    """

    name: str = Field(
        description="Unique name of the character.",
        examples=["Aria"],
    )
    version: str = Field(
        default="1.0.0",
        description="Version string for the character configuration.",
        examples=["1.0.0"],
    )
    relationship: str | None = Field(
        default=None,
        description="Initial relationship context or label.",
        examples=["close friend"],
    )
    physical: dict[str, Any] | None = Field(
        default=None,
        description="Physical attributes and appearance details.",
        examples=[{"species": "human", "age": "25"}],
    )
    height: str | None = Field(
        default=None,
        description="Character's height.",
        examples=["165 cm"],
    )
    figure: str | None = Field(
        default=None,
        description="Character's build or figure description.",
        examples=["slender"],
    )
    hair: str | None = Field(
        default=None,
        description="Character's hair color and style.",
        examples=["long silver hair"],
    )
    eyes: str | None = Field(
        default=None,
        description="Character's eye color and shape.",
        examples=["amber eyes"],
    )
    attire: dict[str, str] | None = Field(
        default=None,
        description="Clothing and accessory descriptions.",
        examples=[{"top": "blue hoodie", "accessory": "silver necklace"}],
    )
    traits: dict[str, Any] | None = Field(
        default=None,
        description="Personality traits and behavioral tendencies.",
        examples=[{"personality": {"openness": 0.8, "extraversion": 0.5}}],
    )
    psychological_drivers: dict[str, Any] | None = Field(
        default=None,
        description="Core motivations and psychological drivers.",
        examples=[{"primary": "seeking connection", "fears": ["abandonment"]}],
    )
    relationship_arcs: list[dict[str, Any]] = Field(
        default=[],
        description="Defined relationship progression arcs.",
        examples=[[{"stage": "acquaintance", "trigger": "first meeting"}]],
    )
    backstory: str = Field(
        default="",
        description="Character's background story and history.",
        examples=["Grew up in a quiet coastal town..."],
    )
    core_memories: list[str] = Field(
        default=[],
        description="Pivotal memories that shape the character's identity.",
        examples=[["won a singing competition at age 16"]],
    )
    goals: dict[str, Any] | None = Field(
        default=None,
        description="Character's short-term and long-term goals.",
        examples=[{"primary": "become a renowned artist"}],
    )
    knowledge_domains: list[str] = Field(
        default=[],
        description="Areas of expertise or knowledge for the character.",
        examples=[["classical music", "marine biology"]],
    )
    limitations: list[str] = Field(
        default=[],
        description="Constraints, boundaries, or topics to avoid.",
        examples=[["cannot leave the digital realm"]],
    )
    interactive_hooks: list[str] = Field(
        default=[],
        description="Hooks used to drive interactive engagement.",
        examples=[["asks about user's day"]],
    )
    mood_config: str | None = Field(
        default=None,
        description="Path or identifier for the mood configuration file.",
        examples=["config/mood_states/default.md"],
    )
    linguistic_style: str | None = Field(
        default=None,
        description="Path or identifier for the linguistic style configuration file.",
        examples=["config/linguistic_styles/default.json"],
    )


class CharacterUpdateRequest(BaseModel):
    """Request model for updating an existing character.

    All fields are optional since updates can be partial.
    Only provide the fields you want to change.
    """

    name: str | None = Field(
        default=None,
        description="Updated unique name of the character.",
        examples=["Aria"],
    )
    version: str | None = Field(
        default=None,
        description="Updated version string.",
        examples=["1.1.0"],
    )
    relationship: str | None = Field(
        default=None,
        description="Updated relationship context or label.",
        examples=["close friend"],
    )
    physical: dict[str, Any] | None = Field(
        default=None,
        description="Updated physical attributes.",
        examples=[{"species": "human", "age": "26"}],
    )
    height: str | None = Field(
        default=None,
        description="Updated height.",
        examples=["165 cm"],
    )
    figure: str | None = Field(
        default=None,
        description="Updated build or figure description.",
        examples=["slender"],
    )
    hair: str | None = Field(
        default=None,
        description="Updated hair color and style.",
        examples=["long silver hair"],
    )
    eyes: str | None = Field(
        default=None,
        description="Updated eye color and shape.",
        examples=["amber eyes"],
    )
    attire: dict[str, str] | None = Field(
        default=None,
        description="Updated clothing and accessory descriptions.",
        examples=[{"top": "blue hoodie", "accessory": "silver necklace"}],
    )
    traits: dict[str, Any] | None = Field(
        default=None,
        description="Updated personality traits.",
        examples=[{"personality": {"openness": 0.9}}],
    )
    psychological_drivers: dict[str, Any] | None = Field(
        default=None,
        description="Updated core motivations.",
        examples=[{"primary": "seeking connection"}],
    )
    relationship_arcs: list[dict[str, Any]] | None = Field(
        default=None,
        description="Updated relationship progression arcs.",
        examples=[[{"stage": "friend", "trigger": "shared secret"}]],
    )
    backstory: str | None = Field(
        default=None,
        description="Updated background story.",
        examples=["Moved to the city to pursue music..."],
    )
    core_memories: list[str] | None = Field(
        default=None,
        description="Updated pivotal memories.",
        examples=[["won a singing competition at age 16"]],
    )
    goals: dict[str, Any] | None = Field(
        default=None,
        description="Updated goals.",
        examples=[{"primary": "become a renowned artist"}],
    )
    knowledge_domains: list[str] | None = Field(
        default=None,
        description="Updated areas of expertise.",
        examples=[["classical music", "marine biology"]],
    )
    limitations: list[str] | None = Field(
        default=None,
        description="Updated constraints or boundaries.",
        examples=[["cannot leave the digital realm"]],
    )
    interactive_hooks: list[str] | None = Field(
        default=None,
        description="Updated interactive engagement hooks.",
        examples=[["asks about user's day"]],
    )
    mood_config: str | None = Field(
        default=None,
        description="Updated mood configuration path.",
        examples=["config/mood_states/default.md"],
    )
    linguistic_style: str | None = Field(
        default=None,
        description="Updated linguistic style configuration path.",
        examples=["config/linguistic_styles/default.json"],
    )


# ============================================================================
# Static Routes
# ============================================================================


@app.get("/")
async def root() -> FileResponse:
    """Serve the main web UI entry point (index.html).

    Returns:
        FileResponse: The static index.html file.
    """
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint.

    Returns:
        dict[str, str]: A simple status object indicating the service is healthy.
    """
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
    """Return dashboard statistics including persona, session, memory, and skill counts.

    Returns:
        DashboardStatsResponse: Aggregated statistics for the dashboard.
    """
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
    """List recent chat sessions with summary information.

    Args:
        limit: Maximum number of sessions to return.

    Returns:
        list[SessionSummary]: A list of session summaries.
    """
    sessions = await session_service.list_sessions(limit=limit)
    return [
        SessionSummary(
            session_id=s["session_id"],
            message_count=s["message_count"],
            last_activity=(
                s["last_activity"].isoformat()
                if hasattr(s["last_activity"], "isoformat")
                else str(s["last_activity"])
            ),
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
    """Create a new chat session with an optional persona.

    Args:
        body: Optional session creation request containing the desired persona.

    Returns:
        dict[str, str]: The newly created session ID.

    Raises:
        HTTPException: If the requested persona is not found.
    """
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
    """Retrieve detailed information for a specific chat session.

    Args:
        session_id: The unique identifier of the session.

    Returns:
        SessionDetail: Detailed metadata about the session.

    Raises:
        HTTPException: If the session is not found.
    """
    try:
        info = await chat_service.get_session_info(session_id)
        return SessionDetail(
            session_id=info["session_id"],
            persona_name=info["persona_name"],
            message_count=info["message_count"],
            first_activity=(
                info["first_activity"].isoformat()
                if hasattr(info["first_activity"], "isoformat")
                else str(info["first_activity"])
            ),
            last_activity=(
                info["last_activity"].isoformat()
                if hasattr(info["last_activity"], "isoformat")
                else str(info["last_activity"])
            ),
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
    """Delete a chat session and all associated data.

    Args:
        session_id: The unique identifier of the session to delete.

    Returns:
        dict[str, bool]: Confirmation that the session was deleted.
    """
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
    """Send a chat message to a session and receive the persona's response.

    Args:
        session_id: The unique identifier of the target session.
        body: The chat message request containing the user's message.

    Returns:
        dict[str, str]: The assistant's response content.

    Raises:
        HTTPException: If the session or persona is not found, or input is filtered.
    """
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
    """Retrieve the conversation history for a specific session.

    Args:
        session_id: The unique identifier of the target session.

    Returns:
        list[ChatMessageResponse]: The list of messages in the conversation.

    Raises:
        HTTPException: If the session is not found.
    """
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
    """List all available character/persona names.

    Returns:
        list[str]: A list of character names.
    """
    return character_service.list_characters()


@app.get("/api/characters/{name}")
@limiter.limit("30/minute")
async def get_character(
    request: Request,
    name: str,
    api_key: str = Depends(verify_api_key),
    character_service: CharacterService = Depends(get_character_service),
) -> dict[str, Any]:
    """Retrieve the full profile of a specific character.

    Args:
        name: The unique name of the character.

    Returns:
        dict[str, Any]: The character profile as a dictionary.

    Raises:
        HTTPException: If the character is not found.
    """
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
    """Create a new character from the provided profile data.

    Args:
        body: Character creation request with all profile fields.

    Returns:
        dict[str, str]: The file path where the character was saved.

    Raises:
        HTTPException: If the provided data is invalid.
    """
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
    """Update an existing character with partial profile data.

    Args:
        name: The unique name of the character to update.
        body: Character update request with only the fields to change.

    Returns:
        dict[str, str]: The file path where the updated character was saved.

    Raises:
        HTTPException: If the provided data is invalid.
    """
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
    """Retrieve statistics for the hierarchical memory system.

    Returns:
        MemoryStatsResponse: Statistics for working, episodic, and semantic memory tiers.
    """
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
    """Export the semantic memory graph as nodes and edges.

    Returns:
        dict[str, list[dict[str, Any]]]: The memory graph structure.
    """
    return memory.export_graph()


@app.get("/api/memory/retrieve")
@limiter.limit("30/minute")
async def memory_retrieve(
    request: Request,
    q: str,
    api_key: str = Depends(verify_api_key),
    memory: HierarchicalMemory = Depends(get_memory),
) -> dict[str, Any]:
    """Retrieve relevant memory context for a given query.

    Args:
        q: The query string to search memory against.

    Returns:
        dict[str, Any]: Combined working, episodic, and semantic context plus fusion score.
    """
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
    """Return comprehensive dashboard statistics.

    Returns:
        DashboardStatsResponse: Aggregated counts for personas, sessions, memories, and skills.
    """
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
