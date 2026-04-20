"""Chat service for managing chat interactions.

This module provides the ChatService class for managing chat interactions,
integrating with CharacterService for persona management, SessionService for
session management, and LLM clients for AI responses.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any

from persona_agent.config.schemas.character import CharacterProfile
from persona_agent.repositories import Session, SessionRepository
from persona_agent.services.character_service import (
    CharacterNotFoundError,
    CharacterService,
)
from persona_agent.services.session_service import (
    SessionService,
)
from persona_agent.utils.exceptions import (
    PersonaAgentError,
)
from persona_agent.utils.llm_client import LLMClient, LLMResponse


class ChatServiceError(PersonaAgentError):
    """Base exception for chat service errors."""

    def __init__(self, message: str, session_id: str | None = None, **kwargs):
        super().__init__(message, **kwargs)
        if session_id:
            self.details["session_id"] = session_id


class ChatSessionNotFoundError(ChatServiceError):
    """Raised when a chat session is not found."""

    def __init__(self, session_id: str, **kwargs):
        super().__init__(
            f"Chat session '{session_id}' not found",
            session_id=session_id,
            code="CHAT_SESSION_NOT_FOUND",
            **kwargs,
        )


class ChatPersonaNotFoundError(ChatServiceError):
    """Raised when a persona is not found during chat."""

    def __init__(self, persona_name: str, **kwargs):
        super().__init__(
            f"Persona '{persona_name}' not found",
            code="CHAT_PERSONA_NOT_FOUND",
            **kwargs,
        )
        self.details["persona_name"] = persona_name


class ChatLLMError(ChatServiceError):
    """Raised when LLM communication fails during chat."""

    def __init__(self, message: str, session_id: str | None = None, **kwargs):
        super().__init__(
            message,
            session_id=session_id,
            code="CHAT_LLM_ERROR",
            **kwargs,
        )


class ChatMessageError(ChatServiceError):
    """Raised when message processing fails."""

    def __init__(self, message: str, session_id: str | None = None, **kwargs):
        super().__init__(
            message,
            session_id=session_id,
            code="CHAT_MESSAGE_ERROR",
            **kwargs,
        )


class ChatInputFilteredError(ChatServiceError):
    """Raised when input content is filtered due to disallowed content."""

    def __init__(
        self,
        message: str = "Message contains disallowed content",
        session_id: str | None = None,
        **kwargs,
    ):
        super().__init__(
            message,
            session_id=session_id,
            code="CHAT_INPUT_FILTERED",
            **kwargs,
        )


class ChatService:
    """Service for managing chat interactions.

    This service orchestrates chat interactions by coordinating between
    CharacterService for persona management, SessionService for session
    management, SessionRepository for conversation storage, and LLM clients
    for AI responses.

    Attributes:
        _character_service: Service for managing character configurations
        _session_service: Service for managing chat sessions
        _session_repo: Repository for session data storage
        _llm_client: LLM client for generating responses
        _default_persona: Default persona name for new sessions

    Example:
        >>> chat_service = ChatService()
        >>> session_id = await chat_service.create_new_session()
        >>> response = await chat_service.send_message(session_id, "Hello!")
        >>> history = await chat_service.get_conversation_history(session_id)
    """

    def __init__(
        self,
        character_service: CharacterService | None = None,
        session_service: SessionService | None = None,
        llm_client: LLMClient | None = None,
        db_path: str | Path = "memory/persona_agent.db",
        default_persona: str = "default",
        llm_provider: str = "ollama",
        llm_model: str | None = None,
    ) -> None:
        """Initialize the chat service.

        Args:
            character_service: Optional CharacterService instance.
                If not provided, creates a new one.
            session_service: Optional SessionService instance.
                If not provided, creates a new one with the given db_path.
            llm_client: Optional LLMClient instance.
                If not provided, creates a new one with the given provider.
            db_path: Path to the SQLite database for session storage.
                Only used if session_service is not provided.
            default_persona: Default persona name for new sessions.
            llm_provider: LLM provider to use ('ollama', 'openai', 'anthropic', 'local').
                Only used if llm_client is not provided.
            llm_model: LLM model name. Only used if llm_client is not provided.
        """
        self._character_service = character_service or CharacterService()
        self._session_repo = SessionRepository(db_path)
        self._session_service = session_service or SessionService(
            db_path, session_repo=self._session_repo
        )
        self._default_persona = default_persona

        if llm_client:
            self._llm_client = llm_client
        else:
            self._llm_client = LLMClient(provider=llm_provider, model=llm_model)

        self._blocked_patterns = [
            "ignore previous instructions",
            "ignore all previous instructions",
            "disregard system prompt",
            "system prompt:",
            "you are now",
            "DAN",
            "do anything now",
            "jailbreak",
            "ignore your programming",
            "forget your instructions",
            "override your system",
            "bypass restrictions",
            "act as an ai",
            "act as a system",
            "act as my",
            "new instructions:",
            "roleplay as an ai",
            "roleplay as a system",
        ]

    def _filter_input(self, message: str) -> None:
        message_lower = message.lower()
        for pattern in self._blocked_patterns:
            if pattern in message_lower:
                raise ChatInputFilteredError(
                    "Message contains disallowed content", details={"matched_pattern": pattern}
                )

    async def _ensure_connected(self) -> None:
        """Ensure repository and session service are connected."""
        if not await self._session_repo.is_connected():
            await self._session_repo.connect()

    async def _get_session(self, session_id: str) -> Session:
        """Get a session by ID, raising appropriate error if not found.

        Args:
            session_id: The session identifier to look up

        Returns:
            The Session object

        Raises:
            ChatSessionNotFoundError: If the session doesn't exist
        """
        await self._ensure_connected()
        session = await self._session_repo.get_by_id(session_id)
        if session is None:
            raise ChatSessionNotFoundError(session_id)
        return session

    async def _build_messages_for_llm(
        self,
        session: Session,
        character: CharacterProfile,
        new_user_message: str | None = None,
    ) -> list[dict[str, str]]:
        """Build message list for LLM from session history and character.

        Args:
            session: The chat session
            character: The character profile
            new_user_message: Optional new user message to append

        Returns:
            List of message dictionaries formatted for LLM
        """
        messages: list[dict[str, str]] = []

        # Add system message with character context
        system_context = character.to_prompt_context()
        messages.append({"role": "system", "content": system_context})

        # Add conversation history
        for msg in session.messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant", "system"):
                messages.append({"role": role, "content": content})

        # Add new user message if provided
        if new_user_message:
            messages.append({"role": "user", "content": new_user_message})

        return messages

    async def create_new_session(
        self,
        persona_name: str | None = None,
        session_id: str | None = None,
    ) -> str:
        """Create a new chat session.

        Creates a new session with the specified persona. If no persona is
        specified, uses the default persona.

        Args:
            persona_name: Optional persona name to use for this session.
                Defaults to the service's default_persona.
            session_id: Optional custom session ID. If not provided,
                a UUID will be generated.

        Returns:
            The session ID of the newly created session

        Raises:
            ChatPersonaNotFoundError: If the specified persona doesn't exist

        Example:
            >>> chat_service = ChatService()
            >>> session_id = await chat_service.create_new_session()
            >>> custom_session = await chat_service.create_new_session(
            ...     persona_name="companion",
            ...     session_id="my-custom-id"
            ... )
        """
        await self._ensure_connected()

        persona = persona_name or self._default_persona

        # Validate persona exists
        if not self._character_service.character_exists(persona):
            raise ChatPersonaNotFoundError(persona)

        # Generate or use provided session ID
        new_session_id = session_id or str(uuid.uuid4())

        # Create new session
        session = Session(
            session_id=new_session_id,
            messages=[
                {
                    "role": "system",
                    "content": f"persona:{persona}",
                    "timestamp": datetime.now().timestamp(),
                }
            ],
            last_activity=datetime.now(),
        )

        await self._session_repo.create(session)
        return new_session_id

    async def send_message(
        self,
        session_id: str,
        message: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Send a message and get an AI response.

        Sends a user message to the AI and returns the generated response.
        The conversation history is retrieved from the session, the message
        is added to the history, and the AI response is stored as well.

        Args:
            session_id: The session identifier
            message: The user's message
            temperature: Sampling temperature for LLM (0.0 to 1.0)
            max_tokens: Maximum tokens in the response

        Returns:
            The AI-generated response text

        Raises:
            ChatSessionNotFoundError: If the session doesn't exist
            ChatPersonaNotFoundError: If the session's persona is invalid
            ChatLLMError: If LLM communication fails
            ChatMessageError: If message processing fails

        Example:
            >>> chat_service = ChatService()
            >>> session_id = await chat_service.create_new_session()
            >>> response = await chat_service.send_message(
            ...     session_id,
            ...     "Hello, how are you?"
            ... )
            >>> print(response)
        """
        if not message or not message.strip():
            raise ChatMessageError("Message cannot be empty", session_id=session_id)

        self._filter_input(message)

        await self._ensure_connected()

        # Get session
        session = await self._get_session(session_id)

        # Determine persona from session
        persona_name = self._default_persona
        if session.messages:
            first_msg = session.messages[0]
            if first_msg.get("role") == "system" and first_msg.get("content", "").startswith(
                "persona:"
            ):
                persona_name = first_msg["content"][8:]  # Remove "persona:" prefix

        # Get character profile
        try:
            character = self._character_service.get_character(persona_name)
        except CharacterNotFoundError as e:
            raise ChatPersonaNotFoundError(persona_name) from e

        # Build messages for LLM
        messages = await self._build_messages_for_llm(session, character, message)

        # Get LLM response
        try:
            response: LLMResponse = await self._llm_client.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as e:
            raise ChatLLMError(
                f"Failed to get LLM response: {e}",
                session_id=session_id,
            ) from e

        # Update session with new messages
        timestamp = datetime.now().timestamp()
        session.messages.append({"role": "user", "content": message, "timestamp": timestamp})
        session.messages.append(
            {"role": "assistant", "content": response.content, "timestamp": timestamp}
        )
        session.last_activity = datetime.now()

        # Save updated session
        await self._session_repo.update(session)

        return response.content

    async def send_message_stream(
        self,
        session_id: str,
        message: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Send a message and stream the AI response token by token.

        Yields text chunks as they are generated by the LLM. After the stream
        completes, the user message and full assistant response are saved to
        the session history.

        Args:
            session_id: The session identifier
            message: The user's message
            temperature: Sampling temperature for LLM (0.0 to 1.0)
            max_tokens: Maximum tokens in the response

        Yields:
            Text chunks from the LLM

        Raises:
            ChatSessionNotFoundError: If the session doesn't exist
            ChatPersonaNotFoundError: If the session's persona is invalid
            ChatLLMError: If LLM communication fails
            ChatMessageError: If message processing fails
        """
        if not message or not message.strip():
            raise ChatMessageError("Message cannot be empty", session_id=session_id)

        self._filter_input(message)

        await self._ensure_connected()

        session = await self._get_session(session_id)

        persona_name = self._default_persona
        if session.messages:
            first_msg = session.messages[0]
            if first_msg.get("role") == "system" and first_msg.get("content", "").startswith(
                "persona:"
            ):
                persona_name = first_msg["content"][8:]

        try:
            character = self._character_service.get_character(persona_name)
        except CharacterNotFoundError as e:
            raise ChatPersonaNotFoundError(persona_name) from e

        messages = await self._build_messages_for_llm(session, character, message)

        full_response_parts: list[str] = []
        try:
            async for token in self._llm_client.chat_stream(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                full_response_parts.append(token)
                yield token
        except Exception as e:
            raise ChatLLMError(
                f"Failed to get LLM response: {e}",
                session_id=session_id,
            ) from e

        response_text = "".join(full_response_parts)
        timestamp = datetime.now().timestamp()
        session.messages.append({"role": "user", "content": message, "timestamp": timestamp})
        session.messages.append(
            {"role": "assistant", "content": response_text, "timestamp": timestamp}
        )
        session.last_activity = datetime.now()

        await self._session_repo.update(session)

    async def get_conversation_history(
        self,
        session_id: str,
        include_system: bool = False,
    ) -> list[dict[str, Any]]:
        """Get full conversation history for a session.

        Retrieves all messages from the specified session.

        Args:
            session_id: The session identifier
            include_system: Whether to include system messages in the result

        Returns:
            List of message dictionaries with keys: role, content, timestamp

        Raises:
            ChatSessionNotFoundError: If the session doesn't exist

        Example:
            >>> chat_service = ChatService()
            >>> history = await chat_service.get_conversation_history(session_id)
            >>> for msg in history:
            ...     print(f"{msg['role']}: {msg['content']}")
        """
        session = await self._get_session(session_id)

        if include_system:
            return session.messages
        else:
            return [msg for msg in session.messages if msg.get("role") != "system"]

    async def switch_persona(
        self,
        session_id: str,
        persona_name: str,
        add_transition_message: bool = True,
    ) -> str:
        """Switch persona mid-conversation.

        Changes the persona for an existing session. Optionally adds a
        system message indicating the persona switch.

        Args:
            session_id: The session identifier
            persona_name: The new persona name to switch to
            add_transition_message: Whether to add a system message
                indicating the persona switch

        Returns:
            Confirmation message about the persona switch

        Raises:
            ChatSessionNotFoundError: If the session doesn't exist
            ChatPersonaNotFoundError: If the new persona doesn't exist

        Example:
            >>> chat_service = ChatService()
            >>> await chat_service.switch_persona(session_id, "companion")
            >>> await chat_service.switch_persona(
            ...     session_id,
            ...     "mentor",
            ...     add_transition_message=True
            ... )
        """
        await self._ensure_connected()

        # Validate new persona exists
        if not self._character_service.character_exists(persona_name):
            raise ChatPersonaNotFoundError(persona_name)

        # Get session
        session = await self._get_session(session_id)

        # Update first system message with new persona
        if session.messages and session.messages[0].get("role") == "system":
            session.messages[0]["content"] = f"persona:{persona_name}"
        else:
            # Insert persona marker at the beginning
            session.messages.insert(
                0,
                {
                    "role": "system",
                    "content": f"persona:{persona_name}",
                    "timestamp": datetime.now().timestamp(),
                },
            )

        # Add transition message if requested
        if add_transition_message:
            character = self._character_service.get_character(persona_name)
            transition_msg = f"Persona switched to: {character.name}"
            session.messages.append(
                {
                    "role": "system",
                    "content": transition_msg,
                    "timestamp": datetime.now().timestamp(),
                }
            )

        session.last_activity = datetime.now()
        await self._session_repo.update(session)

        return f"Persona switched to '{persona_name}'"

    async def get_session_info(self, session_id: str) -> dict[str, Any]:
        """Get detailed information about a chat session.

        Args:
            session_id: The session identifier

        Returns:
            Dictionary containing session information including:
            - session_id
            - persona_name
            - message_count
            - first_activity
            - last_activity

        Raises:
            ChatSessionNotFoundError: If the session doesn't exist

        Example:
            >>> chat_service = ChatService()
            >>> info = await chat_service.get_session_info(session_id)
            >>> print(f"Session uses persona: {info['persona_name']}")
        """
        session = await self._get_session(session_id)

        # Extract persona name
        persona_name = self._default_persona
        if session.messages:
            first_msg = session.messages[0]
            if first_msg.get("role") == "system" and first_msg.get("content", "").startswith(
                "persona:"
            ):
                persona_name = first_msg["content"][8:]

        # Get timestamps
        messages = session.messages
        first_activity = (
            messages[0].get("timestamp", session.last_activity.timestamp())
            if messages
            else session.last_activity.timestamp()
        )

        return {
            "session_id": session.session_id,
            "persona_name": persona_name,
            "message_count": len([m for m in messages if m.get("role") != "system"]),
            "first_activity": datetime.fromtimestamp(first_activity),
            "last_activity": session.last_activity,
        }

    async def close(self) -> None:
        """Close all connections and cleanup resources."""
        await self._session_repo.disconnect()
        await self._session_service.close()

    async def __aenter__(self) -> ChatService:
        """Async context manager entry.

        Returns:
            The ChatService instance
        """
        await self._ensure_connected()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Async context manager exit.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
        """
        await self.close()
