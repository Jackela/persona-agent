"""MCP (Model Context Protocol) integration for external tools.

MCP allows the agent to connect to external services like:
- Search engines
- Databases
- File systems
- Custom APIs
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MCPToolResult:
    """Result from an MCP tool execution."""

    success: bool
    data: Any
    error: str | None = None


class MCPTool(ABC):
    """Base class for MCP tools.

    Tools provide specific capabilities that can be invoked by the agent.
    """

    name: str = ""
    description: str = ""

    @abstractmethod
    async def execute(self, **params: Any) -> MCPToolResult:
        """Execute the tool with given parameters.

        Args:
            **params: Tool-specific parameters

        Returns:
            MCPToolResult with the execution result
        """
        pass

    def get_schema(self) -> dict[str, Any]:
        """Get the tool's JSON schema for parameter validation."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {},
        }


class MCPClient:
    """Client for managing and executing MCP tools.

    Acts as a registry and executor for available tools.
    """

    def __init__(self):
        """Initialize the MCP client."""
        self._tools: dict[str, MCPTool] = {}

    def register_tool(self, tool: MCPTool) -> None:
        """Register a tool with the client.

        Args:
            tool: Tool instance to register
        """
        if not tool.name:
            raise ValueError("Tool must have a name")

        self._tools[tool.name] = tool
        logger.debug(f"Registered MCP tool: {tool.name}")

    def get_tool(self, name: str) -> MCPTool | None:
        """Get a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        """List all registered tools.

        Returns:
            List of tool schemas
        """
        return [tool.get_schema() for tool in self._tools.values()]

    async def execute(self, tool_name: str, **params: Any) -> MCPToolResult:
        """Execute a tool by name.

        Args:
            tool_name: Name of the tool to execute
            **params: Parameters to pass to the tool

        Returns:
            MCPToolResult
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return MCPToolResult(
                success=False,
                data=None,
                error=f"Tool not found: {tool_name}",
            )

        try:
            return await tool.execute(**params)
        except (ConnectionError, ValueError) as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return MCPToolResult(
                success=False,
                data=None,
                error=str(e),
            )


# Built-in tools


class WebSearchTool(MCPTool):
    """Tool for web search (mock implementation)."""

    name = "web_search"
    description = "Search the web for information"

    async def execute(self, query: str, limit: int = 5) -> MCPToolResult:
        """Execute web search.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            Search results
        """
        # Mock implementation - in production, integrate with search API
        logger.info(f"Mock web search: {query}")
        return MCPToolResult(
            success=True,
            data={
                "query": query,
                "results": [
                    {"title": f"Result {i}", "url": f"https://example.com/{i}"}
                    for i in range(min(limit, 3))
                ],
            },
        )

    def get_schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        }


class CalculatorTool(MCPTool):
    """Tool for mathematical calculations."""

    name = "calculator"
    description = "Perform mathematical calculations"

    async def execute(self, expression: str) -> MCPToolResult:
        """Execute calculation using safe evaluation."""
        try:
            # Use ast module for safe parsing
            import ast
            import operator

            # Define allowed operators
            allowed_operators = {
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Div: operator.truediv,
                ast.Pow: operator.pow,
                ast.USub: operator.neg,
            }

            # Define allowed functions
            allowed_functions = {
                "abs": abs,
                "max": max,
                "min": min,
                "round": round,
                "sum": sum,
                "pow": pow,
            }

            # Security: validate no dangerous characters
            dangerous = ["import", "exec", "eval", "compile", "__"]
            expr_lower = expression.lower()
            for d in dangerous:
                if d in expr_lower:
                    return MCPToolResult(
                        success=False,
                        data=None,
                        error=f"Expression contains forbidden keyword: {d}",
                    )

            # Parse the expression
            tree = ast.parse(expression, mode="eval")

            def eval_node(node):
                if isinstance(node, ast.Num):  # Python 3.7 compatibility
                    return node.n
                elif isinstance(node, ast.Constant):  # Python 3.8+
                    return node.value
                elif isinstance(node, ast.BinOp):
                    op_type = type(node.op)
                    if op_type not in allowed_operators:
                        raise ValueError(f"Operator not allowed: {op_type.__name__}")
                    left = eval_node(node.left)
                    right = eval_node(node.right)
                    return allowed_operators[op_type](left, right)
                elif isinstance(node, ast.UnaryOp):
                    op_type = type(node.op)
                    if op_type not in allowed_operators:
                        raise ValueError(f"Unary operator not allowed: {op_type.__name__}")
                    operand = eval_node(node.operand)
                    return allowed_operators[op_type](operand)
                elif isinstance(node, ast.Call):
                    if not isinstance(node.func, ast.Name):
                        raise ValueError("Complex function calls not allowed")
                    func_name = node.func.id
                    if func_name not in allowed_functions:
                        raise ValueError(f"Function not allowed: {func_name}")
                    args = [eval_node(arg) for arg in node.args]
                    return allowed_functions[func_name](*args)
                elif isinstance(node, ast.Name):
                    raise ValueError(f"Variables not allowed: {node.id}")
                else:
                    raise ValueError(f"Node type not allowed: {type(node).__name__}")

            result = eval_node(tree.body)
            return MCPToolResult(success=True, data={"result": result})
        except (ConnectionError, ValueError, SyntaxError) as e:
            return MCPToolResult(
                success=False,
                data=None,
                error=f"Calculation error: {e}",
            )


class MemoryTool(MCPTool):
    """Tool for accessing conversation memory."""

    name = "memory"
    description = "Access previous conversation history and user information"

    def __init__(self, memory_store: Any = None):
        """Initialize with memory store.

        Args:
            memory_store: Memory store instance
        """
        super().__init__()
        self.memory_store = memory_store

    async def execute(
        self,
        operation: str,
        session_id: str | None = None,
        query: str | None = None,
        limit: int = 5,
    ) -> MCPToolResult:
        """Execute memory operation.

        Args:
            operation: Operation type (recent, relevant, user)
            session_id: Session ID for context
            query: Search query for relevant memories
            limit: Maximum results

        Returns:
            Memory data
        """
        if not self.memory_store:
            return MCPToolResult(
                success=False,
                data=None,
                error="Memory store not configured",
            )

        try:
            if operation == "recent":
                memories = await self.memory_store.retrieve_recent(session_id or "default", limit)
                return MCPToolResult(
                    success=True,
                    data={
                        "memories": [
                            {
                                "user": m.user_message,
                                "assistant": m.assistant_message,
                            }
                            for m in memories
                        ]
                    },
                )
            elif operation == "relevant":
                if not query:
                    return MCPToolResult(
                        success=False,
                        data=None,
                        error="Query required for relevant search",
                    )
                memories = await self.memory_store.retrieve_relevant(query, session_id, limit)
                return MCPToolResult(success=True, data={"memories": memories})
            else:
                return MCPToolResult(
                    success=False,
                    data=None,
                    error=f"Unknown operation: {operation}",
                )
        except (ConnectionError, ValueError) as e:
            return MCPToolResult(success=False, data=None, error=str(e))

    def get_schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["recent", "relevant", "user"],
                        "description": "Type of memory operation",
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Session identifier",
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query for relevant memories",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 5,
                    },
                },
                "required": ["operation"],
            },
        }


# Global instance
_mcp_client: MCPClient | None = None


def get_mcp_client(memory_store=None) -> MCPClient:
    """Get the global MCP client instance.

    Args:
        memory_store: Optional memory store for MemoryTool

    Returns:
        Configured MCPClient instance
    """
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
        # Register built-in tools
        _mcp_client.register_tool(WebSearchTool())
        _mcp_client.register_tool(CalculatorTool())
        _mcp_client.register_tool(MemoryTool(memory_store=memory_store))
    return _mcp_client
