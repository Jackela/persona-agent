"""LLM client for persona-agent.

Supports multiple LLM providers:
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Local models (via OpenAI-compatible API)
"""

import os
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

import httpx


class LLMResponse:
    """LLM response wrapper."""

    def __init__(self, content: str, model: str, usage: dict | None = None):
        self.content = content
        self.model = model
        self.usage = usage or {}


class BaseLLMClient(ABC):
    """Base class for LLM clients."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Send chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name
            temperature: Sampling temperature
            max_tokens: Max tokens to generate

        Returns:
            LLMResponse
        """
        pass

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Stream chat completion.

        Args:
            messages: List of message dicts
            model: Model name
            temperature: Sampling temperature
            max_tokens: Max tokens

        Yields:
            Text chunks
        """
        pass


class OpenAIClient(BaseLLMClient):
    """OpenAI API client."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        """Initialize OpenAI client.

        Args:
            api_key: API key (defaults to OPENAI_API_KEY env var)
            base_url: Custom base URL for local models
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required")

        self.base_url = base_url or "https://api.openai.com/v1"
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=60.0,
        )

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Send chat request."""
        payload: dict[str, Any] = {
            "model": model or "gpt-4",
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        response = await self.client.post("/chat/completions", json=payload)
        response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        return LLMResponse(content, payload["model"], usage)

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Stream chat response."""
        payload: dict[str, Any] = {
            "model": model or "gpt-4",
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        async with self.client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    # Parse SSE data
                    import json

                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"]
                        if "content" in delta:
                            yield delta["content"]
                    except (json.JSONDecodeError, KeyError):
                        continue


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude API client."""

    def __init__(self, api_key: str | None = None):
        """Initialize Anthropic client.

        Args:
            api_key: API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key required")

        self.client = httpx.AsyncClient(
            base_url="https://api.anthropic.com/v1",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            timeout=60.0,
        )

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Send chat request."""
        # Convert messages to Anthropic format
        system_msg = ""
        chat_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                chat_messages.append(msg)

        payload: dict[str, Any] = {
            "model": model or "claude-3-opus-20240229",
            "messages": chat_messages,
            "temperature": temperature,
            "max_tokens": max_tokens or 1024,
        }
        if system_msg:
            payload["system"] = system_msg

        response = await self.client.post("/messages", json=payload)
        response.raise_for_status()

        data = response.json()
        content = data["content"][0]["text"]
        usage = data.get("usage", {})

        return LLMResponse(content, payload["model"], usage)

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Stream chat response."""
        system_msg = ""
        chat_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                chat_messages.append(msg)

        payload: dict[str, Any] = {
            "model": model or "claude-3-opus-20240229",
            "messages": chat_messages,
            "temperature": temperature,
            "max_tokens": max_tokens or 1024,
            "stream": True,
        }
        if system_msg:
            payload["system"] = system_msg

        async with self.client.stream("POST", "/messages", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    import json

                    try:
                        chunk = json.loads(data)
                        if chunk["type"] == "content_block_delta":
                            yield chunk["delta"]["text"]
                    except (json.JSONDecodeError, KeyError):
                        continue


class OllamaClient(BaseLLMClient):
    """Ollama API client for local LLM inference."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
    ):
        """Initialize Ollama client.

        Args:
            base_url: Ollama API base URL (defaults to OLLAMA_BASE_URL env var or http://localhost:11434)
            model: Model name (defaults to OLLAMA_MODEL env var or qwen2.5)
        """
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.default_model = model or os.getenv("OLLAMA_MODEL", "qwen2.5")
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=60.0)

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Send chat request."""
        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        response = await self.client.post("/api/chat", json=payload)
        response.raise_for_status()

        data = response.json()
        content = data["message"]["content"]
        usage = {
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0),
            "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
        }

        return LLMResponse(
            content=content,
            model=payload["model"],
            usage=usage,
        )

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Stream chat response."""
        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
            },
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        import json

        async with self.client.stream("POST", "/api/chat", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line)
                    msg = chunk.get("message", {})
                    if "content" in msg:
                        yield msg["content"]
                except json.JSONDecodeError:
                    continue


class LLMClient:
    """Unified LLM client supporting multiple providers."""

    def __init__(
        self,
        provider: str = "ollama",
        model: str | None = None,
        api_key: str | None = None,
    ):
        """Initialize LLM client.

        Args:
            provider: 'ollama', 'openai', 'anthropic', or 'local'
            model: Model name
            api_key: API key
        """
        self.provider = provider
        self.model = model

        if provider == "ollama":
            self._client = OllamaClient(model=model)
        elif provider == "openai":
            self._client = OpenAIClient(api_key)
        elif provider == "anthropic":
            self._client = AnthropicClient(api_key)
        elif provider == "local":
            # Local models use OpenAI-compatible API
            base_url = os.getenv("LOCAL_LLM_URL", "http://localhost:8000/v1")
            self._client = OpenAIClient(api_key="dummy", base_url=base_url)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Send chat request."""
        return await self._client.chat(
            messages,
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Stream chat response."""
        async for chunk in self._client.chat_stream(
            messages,
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield chunk
