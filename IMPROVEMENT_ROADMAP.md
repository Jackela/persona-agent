# Persona-Agent Improvement Roadmap

Based on code review and industry research (mem0, griptape, CrewAI), here are specific, actionable improvements.

---

## Phase 1: Critical Fixes (Week 1)

### 1.1 Fix Database Connection Sharing
**Priority**: HIGH  
**Effort**: 2 hours  
**File**: `src/persona_agent/services/chat_service.py`

**Problem**: ChatService creates separate connections for SessionService and SessionRepository.

**Implementation**:
```python
# Modify SessionService to accept external repository
class SessionService:
    def __init__(
        self,
        db_path: str | Path = "memory/persona_agent.db",
        session_repo: SessionRepository | None = None,
    ):
        self._session_repo = session_repo or SessionRepository(db_path)
        
# Modify ChatService to share repository
class ChatService:
    def __init__(self, ..., db_path: str | Path = "memory/persona_agent.db"):
        # Create shared repository first
        self._session_repo = SessionRepository(db_path)
        # Pass to SessionService
        self._session_service = session_service or SessionService(
            db_path, 
            session_repo=self._session_repo
        )
        self._character_service = character_service or CharacterService()
```

**Test**: Run `pytest tests/unit/services/` to verify no regressions.

---

### 1.2 Fix Exception Handling in CLI
**Priority**: HIGH  
**Effort**: 1 hour  
**File**: `src/persona_agent/ui/cli.py`

**Implementation**:
```python
# Replace bare except Exception with specific handlers
from persona_agent.services.chat_service import (
    ChatSessionNotFoundError,
    ChatPersonaNotFoundError,
    ChatLLMError,
    ChatServiceError,
)

async def _chat_async(...) -> None:
    async with ChatService(...) as chat_service:
        try:
            if session:
                try:
                    session_info = await chat_service.get_session_info(session)
                except ChatSessionNotFoundError:
                    formatter.print_error(f"Session '{session}' not found.")
                    return
                except ChatServiceError as e:
                    formatter.print_error(f"Error loading session: {e.message}")
                    logger.error(f"Session load error: {e}", exc_info=True)
                    return
            # ... rest of method
```

**Test**: Manually test CLI with invalid session ID to see proper error message.

---

## Phase 2: Performance Optimizations (Week 2)

### 2.1 Add Database Index
**Priority**: MEDIUM  
**Effort**: 30 minutes  
**File**: `src/persona_agent/repositories/session_repository.py:81-110`

**Implementation**:
```python
def _initialize_schema(self) -> None:
    self._connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            last_activity TIMESTAMP NOT NULL
        );
        
        -- Add index for performance
        CREATE INDEX IF NOT EXISTS idx_sessions_last_activity 
            ON sessions(last_activity DESC);
        
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                ON DELETE CASCADE
        );
        
        CREATE INDEX IF NOT EXISTS idx_messages_session
            ON messages(session_id);
        """
    )
```

**Test**: Benchmark with 1000+ sessions to verify query performance.

---

### 2.2 Optimize Message Update Strategy
**Priority**: MEDIUM  
**Effort**: 3 hours  
**File**: `src/persona_agent/repositories/session_repository.py:214-263`

**Implementation**:
```python
async def update(self, entity: Session) -> Session:
    """Update session with delta tracking."""
    if not self._connection:
        raise ConnectionError("Not connected to database")
    
    # Verify session exists
    cursor = self._connection.execute(
        "SELECT 1 FROM sessions WHERE session_id = ?",
        (entity.session_id,)
    )
    if not cursor.fetchone():
        raise EntityNotFoundError("Session", entity.session_id)
    
    try:
        # Get existing message count to determine new messages
        cursor = self._connection.execute(
            "SELECT COUNT(*) as count FROM messages WHERE session_id = ?",
            (entity.session_id,)
        )
        existing_count = cursor.fetchone()["count"]
        
        # Only insert new messages (append-only strategy)
        new_messages = entity.messages[existing_count:]
        for msg in new_messages:
            self._connection.execute(
                """INSERT INTO messages (session_id, role, content, timestamp)
                   VALUES (?, ?, ?, ?)""",
                (
                    entity.session_id,
                    msg.get("role", "user"),
                    msg.get("content", ""),
                    msg.get("timestamp", datetime.now().timestamp()),
                ),
            )
        
        # Update session timestamp
        self._connection.execute(
            "UPDATE sessions SET last_activity = ? WHERE session_id = ?",
            (entity.last_activity.timestamp(), entity.session_id),
        )
        
        self._connection.commit()
        return entity
    except sqlite3.Error as e:
        raise RepositoryError(f"Failed to update session: {e}")
```

**Test**: Add benchmark test comparing old vs new update strategy.

---

## Phase 3: Code Quality Improvements (Week 3)

### 3.1 Extract Magic Strings to Constants
**Priority**: MEDIUM  
**Effort**: 1 hour  
**Files**: 
- `src/persona_agent/services/chat_service.py`

**Implementation**:
```python
# Add at top of file or in constants module
PERSONA_PREFIX = "persona:"
DEFAULT_PERSONA = "default"
SYSTEM_ROLE = "system"
USER_ROLE = "user"
ASSISTANT_ROLE = "assistant"

class ChatService:
    def _extract_persona_from_message(self, content: str) -> str | None:
        if content.startswith(PERSONA_PREFIX):
            return content[len(PERSONA_PREFIX):]
        return None
    
    async def send_message(...):
        # Use constants
        if first_msg.get("role") == SYSTEM_ROLE:
            persona = self._extract_persona_from_message(content)
```

---

### 3.2 Implement find_by_filters
**Priority**: MEDIUM  
**Effort**: 2 hours  
**File**: `src/persona_agent/repositories/session_repository.py:358-376`

**Implementation**:
```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class QueryFilter:
    field: Literal["session_id", "last_activity_after", "last_activity_before"]
    value: Any

async def find_by_filters(
    self,
    filters: list[QueryFilter],
    pagination: PaginationParams | None = None,
) -> PaginatedResult[Session]:
    """Find sessions matching the given filters.
    
    Example:
        filters = [
            QueryFilter("last_activity_after", datetime(2024, 1, 1).timestamp()),
        ]
        result = await repo.find_by_filters(filters)
    """
    if not self._connection:
        raise ConnectionError("Not connected to database")
    
    pagination = pagination or PaginationParams()
    where_clauses = []
    params = []
    
    for f in filters:
        if f.field == "session_id":
            where_clauses.append("session_id = ?")
            params.append(f.value)
        elif f.field == "last_activity_after":
            where_clauses.append("last_activity > ?")
            params.append(f.value)
        elif f.field == "last_activity_before":
            where_clauses.append("last_activity < ?")
            params.append(f.value)
    
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    # Get total count
    cursor = self._connection.execute(
        f"SELECT COUNT(*) as count FROM sessions WHERE {where_sql}",
        params
    )
    total = cursor.fetchone()["count"]
    
    # Get paginated results
    cursor = self._connection.execute(
        f"""SELECT session_id, last_activity FROM sessions 
            WHERE {where_sql}
            ORDER BY last_activity DESC LIMIT ? OFFSET ?""",
        (*params, pagination.limit, pagination.offset)
    )
    
    sessions = []
    for row in cursor.fetchall():
        messages = await self._get_messages(row["session_id"])
        sessions.append(
            Session(
                session_id=row["session_id"],
                messages=messages,
                last_activity=datetime.fromtimestamp(row["last_activity"]),
            )
        )
    
    return PaginatedResult(
        items=sessions,
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )
```

**Test**: Add unit tests for filter functionality.

---

## Phase 4: Feature Enhancements (Week 4+)

### 4.1 Add Memory Abstraction Layer (From mem0 Pattern)
**Priority**: LOW (but valuable)  
**Effort**: 1 week  
**New File**: `src/persona_agent/memory/base.py`

**Purpose**: Allow swapping storage backends (ChromaDB, SQLite, Redis, etc.)

**Implementation**:
```python
from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel

class MemoryEntry(BaseModel):
    content: str
    metadata: dict[str, Any]
    timestamp: float

class MemoryBase(ABC, BaseModel):
    """Abstract base for memory implementations."""
    
    @abstractmethod
    async def add(self, entry: MemoryEntry) -> None:
        """Add a memory entry."""
        pass
    
    @abstractmethod
    async def search(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        """Search for relevant memories."""
        pass
    
    @abstractmethod
    async def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        """Get recent memories."""
        pass

# Implementations
class SQLiteMemory(MemoryBase):
    """SQLite-based memory storage."""
    db_path: str = "memory/memories.db"
    _connection: Any = None
    
    async def add(self, entry: MemoryEntry) -> None:
        # Implementation
        pass

class ChromaDBMemory(MemoryBase):
    """ChromaDB-based vector memory."""
    collection_name: str = "memories"
    _client: Any = None
    
    async def add(self, entry: MemoryEntry) -> None:
        # Implementation with embeddings
        pass
```

---

### 4.2 Add Conversation Summarization (From griptape Pattern)
**Priority**: LOW  
**Effort**: 3 days  
**New File**: `src/persona_agent/services/summarization_service.py`

**Purpose**: Compress old messages when context window fills up.

**Implementation**:
```python
class SummarizationService:
    """Summarize conversation history to extend memory."""
    
    def __init__(self, llm_client: LLMClient):
        self._llm_client = llm_client
    
    async def summarize_messages(self, messages: list[dict]) -> str:
        """Summarize a list of messages."""
        content = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in messages
        ])
        
        prompt = f"""Summarize the following conversation concisely:

{content}

Summary:"""
        
        response = await self._llm_client.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200
        )
        
        return response.content
    
    async def compress_session(
        self,
        session: Session,
        target_message_count: int = 10
    ) -> Session:
        """Compress session to target message count."""
        if len(session.messages) <= target_message_count:
            return session
        
        # Keep system message and recent messages
        system_msgs = [m for m in session.messages if m.get("role") == "system"]
        recent_msgs = session.messages[-(target_message_count // 2):]
        
        # Summarize middle messages
        middle_msgs = session.messages[len(system_msgs):-(target_message_count // 2)]
        if middle_msgs:
            summary = await self.summarize_messages(middle_msgs)
            summary_msg = {
                "role": "system",
                "content": f"[Earlier conversation summary]: {summary}",
                "timestamp": middle_msgs[0]["timestamp"]
            }
            session.messages = system_msgs + [summary_msg] + recent_msgs
        
        return session
```

---

## Summary

### Week 1: Critical Fixes
- Fix database connection sharing
- Fix exception handling in CLI

### Week 2: Performance
- Add database indexes
- Optimize message updates

### Week 3: Code Quality
- Extract constants
- Implement find_by_filters

### Week 4+: Features
- Memory abstraction layer
- Conversation summarization

**Total Effort**: ~2-3 weeks for all improvements

**Priority Order**: Fix critical issues first, then optimizations, then features.
