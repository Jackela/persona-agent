"""MCP (Model Context Protocol) integration package."""

from persona_agent.mcp.client import (
    MCPClient,
    MCPTool,
    MCPToolResult,
    get_mcp_client,
)

__all__ = [
    "MCPClient",
    "MCPTool",
    "MCPToolResult",
    "get_mcp_client",
]
