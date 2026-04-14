"""Tests for llm_client module with mocked HTTP requests."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from persona_agent.utils.llm_client import (
    AnthropicClient,
    BaseLLMClient,
    LLMClient,
    LLMResponse,
    OllamaClient,
    OpenAIClient,
)


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_basic_response(self):
        """Test basic response creation."""
        response = LLMResponse(content="Hello", model="gpt-4")

        assert response.content == "Hello"
        assert response.model == "gpt-4"
        assert response.usage == {}

    def test_response_with_usage(self):
        """Test response with usage statistics."""
        usage = {"prompt_tokens": 10, "completion_tokens": 20}
        response = LLMResponse(content="Hello", model="gpt-4", usage=usage)

        assert response.usage["prompt_tokens"] == 10
        assert response.usage["completion_tokens"] == 20


class TestBaseLLMClient:
    """Tests for BaseLLMClient abstract class."""

    def test_abstract_methods(self):
        """Test that BaseLLMClient cannot be instantiated directly."""

        with pytest.raises(TypeError):
            BaseLLMClient()


class TestOpenAIClient:
    """Tests for OpenAIClient."""

    @pytest.fixture
    def mock_env_key(self):
        """Mock environment variable for API key."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-12345"}):
            yield

    @pytest.fixture
    def mock_httpx_client(self):
        """Mock httpx.AsyncClient."""
        with patch("persona_agent.utils.llm_client.httpx.AsyncClient") as mock:
            client = AsyncMock()
            mock.return_value = client
            yield client

    def test_init_without_api_key(self):
        """Test initialization without API key raises error."""
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(ValueError, match="API key required"),
        ):
            OpenAIClient()

    def test_init_with_env_key(self, mock_env_key):
        """Test initialization with environment API key."""
        client = OpenAIClient()

        assert client.api_key == "test-key-12345"
        assert client.base_url == "https://api.openai.com/v1"

    def test_init_with_explicit_key(self):
        """Test initialization with explicit API key."""
        client = OpenAIClient(api_key="explicit-key")

        assert client.api_key == "explicit-key"

    def test_init_with_custom_base_url(self, mock_env_key):
        """Test initialization with custom base URL."""
        client = OpenAIClient(base_url="http://localhost:8000/v1")

        assert client.base_url == "http://localhost:8000/v1"

    @pytest.mark.asyncio
    async def test_chat_success(self, mock_env_key, mock_httpx_client):
        """Test successful chat completion."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello, world!"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_httpx_client.post.return_value = mock_response

        client = OpenAIClient()
        client.client = mock_httpx_client

        messages = [{"role": "user", "content": "Hi"}]
        response = await client.chat(messages, model="gpt-4", temperature=0.5)

        assert response.content == "Hello, world!"
        assert response.model == "gpt-4"
        assert response.usage["prompt_tokens"] == 10

        # Verify request
        mock_httpx_client.post.assert_called_once()
        call_args = mock_httpx_client.post.call_args
        assert call_args[0][0] == "/chat/completions"
        assert call_args[1]["json"]["model"] == "gpt-4"
        assert call_args[1]["json"]["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_chat_default_model(self, mock_env_key, mock_httpx_client):
        """Test chat with default model."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}],
            "usage": {},
        }
        mock_httpx_client.post.return_value = mock_response

        client = OpenAIClient()
        client.client = mock_httpx_client

        messages = [{"role": "user", "content": "Hi"}]
        response = await client.chat(messages)

        assert response.model == "gpt-4"

    @pytest.mark.asyncio
    async def test_chat_with_max_tokens(self, mock_env_key, mock_httpx_client):
        """Test chat with max_tokens parameter."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Short"}}],
            "usage": {},
        }
        mock_httpx_client.post.return_value = mock_response

        client = OpenAIClient()
        client.client = mock_httpx_client

        messages = [{"role": "user", "content": "Hi"}]
        await client.chat(messages, max_tokens=100)

        call_args = mock_httpx_client.post.call_args
        assert call_args[1]["json"]["max_tokens"] == 100

    @pytest.mark.asyncio
    async def test_chat_stream(self, mock_env_key, mock_httpx_client):
        """Test streaming chat completion."""
        # Setup mock stream response
        mock_response = MagicMock()

        async def async_lines():
            lines = [
                'data: {"choices": [{"delta": {"content": "Hello"}}]}',
                'data: {"choices": [{"delta": {"content": " world"}}]}',
                "data: [DONE]",
            ]
            for line in lines:
                yield line

        mock_response.aiter_lines = async_lines

        # Configure stream method to return an async context manager mock
        stream_mock = MagicMock()
        stream_mock.__aenter__ = AsyncMock(return_value=mock_response)
        stream_mock.__aexit__ = AsyncMock(return_value=False)
        mock_httpx_client.stream = MagicMock(return_value=stream_mock)

        client = OpenAIClient()
        client.client = mock_httpx_client

        messages = [{"role": "user", "content": "Hi"}]
        chunks = []
        async for chunk in client.chat_stream(messages):
            chunks.append(chunk)

        assert chunks == ["Hello", " world"]


class TestAnthropicClient:
    """Tests for AnthropicClient."""

    @pytest.fixture
    def mock_env_key(self):
        """Mock environment variable for API key."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "anthropic-test-key"}):
            yield

    @pytest.fixture
    def mock_httpx_client(self):
        """Mock httpx.AsyncClient."""
        with patch("persona_agent.utils.llm_client.httpx.AsyncClient") as mock:
            client = AsyncMock()
            mock.return_value = client
            yield client

    def test_init_without_api_key(self):
        """Test initialization without API key raises error."""
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(ValueError, match="API key required"),
        ):
            AnthropicClient()

    def test_init_with_env_key(self, mock_env_key):
        """Test initialization with environment API key."""
        client = AnthropicClient()

        assert client.api_key == "anthropic-test-key"

    def test_init_with_explicit_key(self):
        """Test initialization with explicit API key."""
        client = AnthropicClient(api_key="explicit-key")

        assert client.api_key == "explicit-key"

    @pytest.mark.asyncio
    async def test_chat_success(self, mock_env_key, mock_httpx_client):
        """Test successful chat completion."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [{"text": "Hello from Claude!"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        mock_httpx_client.post.return_value = mock_response

        client = AnthropicClient()
        client.client = mock_httpx_client

        messages = [{"role": "user", "content": "Hi"}]
        response = await client.chat(messages, model="claude-3-opus")

        assert response.content == "Hello from Claude!"
        assert response.model == "claude-3-opus"

    @pytest.mark.asyncio
    async def test_chat_with_system_message(self, mock_env_key, mock_httpx_client):
        """Test chat with system message."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [{"text": "Response"}],
            "usage": {},
        }
        mock_httpx_client.post.return_value = mock_response

        client = AnthropicClient()
        client.client = mock_httpx_client

        messages = [
            {"role": "system", "content": "Be helpful"},
            {"role": "user", "content": "Hi"},
        ]
        await client.chat(messages)

        call_args = mock_httpx_client.post.call_args
        assert call_args[1]["json"]["system"] == "Be helpful"
        assert len(call_args[1]["json"]["messages"]) == 1

    @pytest.mark.asyncio
    async def test_chat_default_max_tokens(self, mock_env_key, mock_httpx_client):
        """Test chat uses default max_tokens."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"content": [{"text": "Response"}]}
        mock_httpx_client.post.return_value = mock_response

        client = AnthropicClient()
        client.client = mock_httpx_client

        messages = [{"role": "user", "content": "Hi"}]
        await client.chat(messages)

        call_args = mock_httpx_client.post.call_args
        assert call_args[1]["json"]["max_tokens"] == 1024

    @pytest.mark.asyncio
    async def test_chat_stream(self, mock_env_key, mock_httpx_client):
        """Test streaming chat completion."""
        mock_response = MagicMock()

        async def async_lines():
            lines = [
                'data: {"type": "content_block_delta", "delta": {"text": "Hello"}}',
                'data: {"type": "content_block_delta", "delta": {"text": " Claude"}}',
            ]
            for line in lines:
                yield line

        mock_response.aiter_lines = async_lines

        # Configure stream method to return an async context manager mock
        stream_mock = MagicMock()
        stream_mock.__aenter__ = AsyncMock(return_value=mock_response)
        stream_mock.__aexit__ = AsyncMock(return_value=False)
        mock_httpx_client.stream = MagicMock(return_value=stream_mock)

        client = AnthropicClient()
        client.client = mock_httpx_client

        messages = [{"role": "user", "content": "Hi"}]
        chunks = []
        async for chunk in client.chat_stream(messages):
            chunks.append(chunk)

        assert chunks == ["Hello", " Claude"]


class TestOllamaClient:
    """Tests for OllamaClient."""

    @pytest.fixture
    def mock_httpx_client(self):
        """Mock httpx.AsyncClient."""
        with patch("persona_agent.utils.llm_client.httpx.AsyncClient") as mock:
            client = AsyncMock()
            mock.return_value = client
            yield client

    def test_init_default_url_and_model(self):
        """Test initialization with default URL and model."""
        with patch.dict(os.environ, {}, clear=True):
            client = OllamaClient()

            assert client.base_url == "http://localhost:11434"
            assert client.default_model == "qwen2.5"

    def test_init_with_custom_url_and_model(self):
        """Test initialization with custom URL and model."""
        client = OllamaClient(base_url="http://ollama:11434", model="llama3.2")

        assert client.base_url == "http://ollama:11434"
        assert client.default_model == "llama3.2"

    def test_init_with_env_vars(self):
        """Test initialization with environment variables."""
        with patch.dict(
            os.environ,
            {"OLLAMA_BASE_URL": "http://host.docker.internal:11434", "OLLAMA_MODEL": "llama3.2"},
        ):
            client = OllamaClient()

            assert client.base_url == "http://host.docker.internal:11434"
            assert client.default_model == "llama3.2"

    @pytest.mark.asyncio
    async def test_chat_success(self, mock_httpx_client):
        """Test successful chat completion."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "model": "qwen2.5",
            "message": {"role": "assistant", "content": "Hello from Ollama!"},
            "done": True,
            "prompt_eval_count": 10,
            "eval_count": 5,
        }
        mock_httpx_client.post.return_value = mock_response

        client = OllamaClient()
        client.client = mock_httpx_client

        messages = [{"role": "user", "content": "Hi"}]
        response = await client.chat(messages, model="qwen2.5", temperature=0.5)

        assert response.content == "Hello from Ollama!"
        assert response.model == "qwen2.5"
        assert response.usage["prompt_tokens"] == 10
        assert response.usage["completion_tokens"] == 5
        assert response.usage["total_tokens"] == 15

        mock_httpx_client.post.assert_called_once()
        call_args = mock_httpx_client.post.call_args
        assert call_args[0][0] == "/api/chat"
        assert call_args[1]["json"]["model"] == "qwen2.5"
        assert call_args[1]["json"]["stream"] is False
        assert call_args[1]["json"]["options"]["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_chat_with_max_tokens(self, mock_httpx_client):
        """Test chat with max_tokens parameter."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "Short"},
            "done": True,
        }
        mock_httpx_client.post.return_value = mock_response

        client = OllamaClient()
        client.client = mock_httpx_client

        messages = [{"role": "user", "content": "Hi"}]
        await client.chat(messages, max_tokens=100)

        call_args = mock_httpx_client.post.call_args
        assert call_args[1]["json"]["options"]["num_predict"] == 100

    @pytest.mark.asyncio
    async def test_chat_stream(self, mock_httpx_client):
        """Test streaming chat completion."""
        mock_response = MagicMock()

        async def async_lines():
            lines = [
                '{"message": {"role": "assistant", "content": "Hello"}}',
                '{"message": {"role": "assistant", "content": " from"}}',
                '{"message": {"role": "assistant", "content": " Ollama"}}',
            ]
            for line in lines:
                yield line

        mock_response.aiter_lines = async_lines

        stream_mock = MagicMock()
        stream_mock.__aenter__ = AsyncMock(return_value=mock_response)
        stream_mock.__aexit__ = AsyncMock(return_value=False)
        mock_httpx_client.stream = MagicMock(return_value=stream_mock)

        client = OllamaClient()
        client.client = mock_httpx_client

        messages = [{"role": "user", "content": "Hi"}]
        chunks = []
        async for chunk in client.chat_stream(messages):
            chunks.append(chunk)

        assert chunks == ["Hello", " from", " Ollama"]


class TestLLMClient:
    """Tests for unified LLMClient."""

    @pytest.fixture
    def mock_env_keys(self):
        """Mock environment variables for API keys."""
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "openai-test-key",
                "ANTHROPIC_API_KEY": "anthropic-test-key",
            },
        ):
            yield

    def test_init_default_provider_is_ollama(self):
        """Test that default provider is ollama."""
        with patch("persona_agent.utils.llm_client.OllamaClient") as mock_ollama:
            client = LLMClient()
            assert client.provider == "ollama"
            mock_ollama.assert_called_once_with(model=None)

    def test_init_ollama(self):
        """Test initialization with Ollama provider."""
        with patch("persona_agent.utils.llm_client.OllamaClient") as mock_ollama:
            LLMClient(provider="ollama", model="qwen2.5")
            mock_ollama.assert_called_once_with(model="qwen2.5")

    def test_init_openai(self, mock_env_keys):
        """Test initialization with OpenAI provider."""
        with patch("persona_agent.utils.llm_client.OpenAIClient") as mock_openai:
            LLMClient(provider="openai", model="gpt-4")
            # Called with None since api_key param defaults to None
            # OpenAIClient reads from env var internally
            mock_openai.assert_called_once_with(None)

    def test_init_anthropic(self, mock_env_keys):
        """Test initialization with Anthropic provider."""
        with patch("persona_agent.utils.llm_client.AnthropicClient") as mock_anthropic:
            LLMClient(provider="anthropic", model="claude-3-opus")
            # Called with None since api_key param defaults to None
            # AnthropicClient reads from env var internally
            mock_anthropic.assert_called_once_with(None)

    def test_init_local(self, mock_env_keys):
        """Test initialization with local provider."""
        with (
            patch("persona_agent.utils.llm_client.OpenAIClient") as mock_openai,
            patch.dict(os.environ, {"LOCAL_LLM_URL": "http://localhost:8080/v1"}),
        ):
            LLMClient(provider="local")

            mock_openai.assert_called_once()
            call_args = mock_openai.call_args
            # Called with api_key="dummy" and base_url from env
            assert call_args.kwargs.get("api_key") == "dummy"
            assert call_args.kwargs.get("base_url") == "http://localhost:8080/v1"

    def test_init_local_default_url(self, mock_env_keys):
        """Test local provider with default URL."""
        with (
            patch("persona_agent.utils.llm_client.OpenAIClient") as mock_openai,
            patch.dict(os.environ, {}, clear=True),
        ):
            LLMClient(provider="local")

            call_args = mock_openai.call_args
            assert call_args.kwargs.get("base_url") == "http://localhost:8000/v1"

    def test_init_unknown_provider(self, mock_env_keys):
        """Test initialization with unknown provider raises error."""
        with pytest.raises(ValueError, match="Unknown provider"):
            LLMClient(provider="unknown")

    @pytest.mark.asyncio
    async def test_chat_delegation(self, mock_env_keys):
        """Test that chat delegates to underlying client."""
        with patch("persona_agent.utils.llm_client.OpenAIClient") as mock_openai:
            mock_instance = AsyncMock()
            mock_instance.chat.return_value = LLMResponse(content="Response", model="gpt-4")
            mock_openai.return_value = mock_instance

            client = LLMClient(provider="openai", model="gpt-4")
            messages = [{"role": "user", "content": "Hi"}]
            response = await client.chat(messages, temperature=0.5)

            assert response.content == "Response"
            mock_instance.chat.assert_called_once_with(
                messages, model="gpt-4", temperature=0.5, max_tokens=None
            )

    @pytest.mark.asyncio
    async def test_chat_stream_delegation(self, mock_env_keys):
        """Test that chat_stream delegates to underlying client."""
        with patch("persona_agent.utils.llm_client.OpenAIClient") as mock_openai:
            mock_instance = AsyncMock()

            async def mock_stream(*args, **kwargs):
                yield "Hello"
                yield " world"

            mock_instance.chat_stream = mock_stream
            mock_openai.return_value = mock_instance

            client = LLMClient(provider="openai", model="gpt-4")
            messages = [{"role": "user", "content": "Hi"}]

            chunks = []
            async for chunk in client.chat_stream(messages, max_tokens=100):
                chunks.append(chunk)

            assert chunks == ["Hello", " world"]
