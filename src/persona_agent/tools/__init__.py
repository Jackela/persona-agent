"""Tool ecosystem for persona-agent.

This package provides a comprehensive set of tools for the agent:
- File operations: read, write, list files
- Code execution: run code in sandboxed environment
- Web search: search the internet for information
- Tool discovery: dynamic tool registration and discovery
- Security: sandboxed execution with resource limits
"""

from persona_agent.tools.base import Tool, ToolContext, ToolResult, ToolSchema
from persona_agent.tools.code_exec import CodeExecutionTool
from persona_agent.tools.discovery import ToolDiscovery, ToolRegistry
from persona_agent.tools.executor import SecurityPolicy, ToolExecutor
from persona_agent.tools.file_ops import FileListTool, FileReadTool, FileWriteTool
from persona_agent.tools.memory_tool import MemoryQueryTool
from persona_agent.tools.web_search import WebSearchTool

__all__ = [
    # Base
    "Tool",
    "ToolContext",
    "ToolResult",
    "ToolSchema",
    # Discovery
    "ToolRegistry",
    "ToolDiscovery",
    # Execution
    "ToolExecutor",
    "SecurityPolicy",
    # Tools
    "FileReadTool",
    "FileWriteTool",
    "FileListTool",
    "CodeExecutionTool",
    "WebSearchTool",
    "MemoryQueryTool",
]
