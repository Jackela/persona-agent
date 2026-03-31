"""Tests for MCP client and tools."""

import pytest

from persona_agent.mcp.client import (
    CalculatorTool,
    MCPClient,
    MCPTool,
    MCPToolResult,
    MemoryTool,
    WebSearchTool,
    get_mcp_client,
)


class TestMCPToolResult:
    """Test MCPToolResult dataclass."""

    def test_success_result(self) -> None:
        """Test successful tool result."""
        result = MCPToolResult(success=True, data={"value": 42})
        assert result.success is True
        assert result.data == {"value": 42}
        assert result.error is None

    def test_failure_result(self) -> None:
        """Test failed tool result."""
        result = MCPToolResult(success=False, data=None, error="Failed")
        assert result.success is False
        assert result.error == "Failed"


class TestMCPClient:
    """Test MCP client functionality."""

    @pytest.fixture
    def client(self) -> MCPClient:
        """Create a fresh MCP client."""
        return MCPClient()

    def test_register_tool(self, client: MCPClient) -> None:
        """Test registering a tool."""
        tool = CalculatorTool()
        client.register_tool(tool)

        assert client.get_tool("calculator") is not None

    def test_register_tool_without_name_raises(self, client: MCPClient) -> None:
        """Test that registering a tool without name raises error."""

        class NoNameTool(MCPTool):
            async def execute(self, **params) -> MCPToolResult:
                return MCPToolResult(success=True, data={})

        with pytest.raises(ValueError, match="must have a name"):
            client.register_tool(NoNameTool())

    def test_get_nonexistent_tool(self, client: MCPClient) -> None:
        """Test getting a tool that doesn't exist."""
        assert client.get_tool("nonexistent") is None

    def test_list_tools(self, client: MCPClient) -> None:
        """Test listing registered tools."""
        client.register_tool(CalculatorTool())
        client.register_tool(WebSearchTool())

        tools = client.list_tools()
        assert len(tools) == 2

        tool_names = [t["name"] for t in tools]
        assert "calculator" in tool_names
        assert "web_search" in tool_names

    @pytest.mark.asyncio
    async def test_execute_tool(self, client: MCPClient) -> None:
        """Test executing a registered tool."""
        client.register_tool(CalculatorTool())

        result = await client.execute("calculator", expression="2 + 2")

        assert result.success is True
        assert result.data["result"] == 4

    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self, client: MCPClient) -> None:
        """Test executing a tool that doesn't exist."""
        result = await client.execute("nonexistent")

        assert result.success is False
        assert "not found" in result.error.lower()


class TestCalculatorTool:
    """Test the calculator tool."""

    @pytest.fixture
    def tool(self) -> CalculatorTool:
        """Create calculator tool."""
        return CalculatorTool()

    @pytest.mark.asyncio
    async def test_addition(self, tool: CalculatorTool) -> None:
        """Test basic addition."""
        result = await tool.execute(expression="2 + 2")
        assert result.success is True
        assert result.data["result"] == 4

    @pytest.mark.asyncio
    async def test_complex_expression(self, tool: CalculatorTool) -> None:
        """Test complex expression."""
        result = await tool.execute(expression="(10 + 5) * 2")
        assert result.success is True
        assert result.data["result"] == 30

    @pytest.mark.asyncio
    async def test_invalid_expression(self, tool: CalculatorTool) -> None:
        """Test invalid expression handling."""
        result = await tool.execute(expression="invalid + +")
        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_builtin_functions(self, tool: CalculatorTool) -> None:
        """Test allowed builtin functions."""
        result = await tool.execute(expression="abs(-5)")
        assert result.success is True
        assert result.data["result"] == 5


class TestWebSearchTool:
    """Test the web search tool."""

    @pytest.fixture
    def tool(self) -> WebSearchTool:
        """Create web search tool."""
        return WebSearchTool()

    @pytest.mark.asyncio
    async def test_search(self, tool: WebSearchTool) -> None:
        """Test basic search."""
        result = await tool.execute(query="python programming", limit=3)

        assert result.success is True
        assert "query" in result.data
        assert "results" in result.data
        assert len(result.data["results"]) <= 3

    def test_schema(self, tool: WebSearchTool) -> None:
        """Test tool schema."""
        schema = tool.get_schema()

        assert schema["name"] == "web_search"
        assert "parameters" in schema
        assert "query" in schema["parameters"]["properties"]


class TestMemoryTool:
    """Test the memory tool."""

    @pytest.mark.asyncio
    async def test_memory_without_store(self) -> None:
        """Test memory tool without memory store."""
        tool = MemoryTool(memory_store=None)

        result = await tool.execute(operation="recent", session_id="test")

        assert result.success is False
        assert "not configured" in result.error.lower()

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_recent_operation(self) -> None:
        """Test recent memories operation."""

        # Mock memory store with async method
        async def mock_retrieve(*args, **kwargs):
            class Mem:
                def __init__(self):
                    self.user_message = "Hello"
                    self.assistant_message = "Hi!"

            return [Mem()]

        mock_store = type(
            "MockStore",
            (),
            {"retrieve_recent": mock_retrieve},
        )()

        tool = MemoryTool(memory_store=mock_store)
        result = await tool.execute(operation="recent", session_id="test")

        assert result.success is True
        assert "memories" in result.data

    @pytest.mark.asyncio
    async def test_relevant_without_query(self) -> None:
        """Test relevant operation without query."""
        mock_store = type("MockStore", (), {})()
        tool = MemoryTool(memory_store=mock_store)

        result = await tool.execute(operation="relevant", session_id="test")

        assert result.success is False
        assert "query required" in result.error.lower()

    @pytest.mark.asyncio
    async def test_unknown_operation(self) -> None:
        """Test unknown operation."""
        mock_store = type("MockStore", (), {})()
        tool = MemoryTool(memory_store=mock_store)

        result = await tool.execute(operation="unknown")

        assert result.success is False
        assert "unknown operation" in result.error.lower()


class TestGlobalMCPClient:
    """Test global MCP client functions."""

    def test_get_mcp_client_singleton(self) -> None:
        """Test that get_mcp_client returns singleton."""
        client1 = get_mcp_client()
        client2 = get_mcp_client()

        assert client1 is client2

    def test_global_client_has_builtin_tools(self) -> None:
        """Test that global client has built-in tools registered."""
        client = get_mcp_client()

        tools = client.list_tools()
        tool_names = [t["name"] for t in tools]

        assert "calculator" in tool_names
        assert "web_search" in tool_names
