"""Memory query tool for accessing conversation history.

Provides tools for retrieving and searching memories.
"""

from __future__ import annotations

from typing import Any

from persona_agent.tools.base import (
    Tool,
    ToolCategory,
    ToolContext,
    ToolResult,
    ToolRiskLevel,
    ToolSchema,
)


class MemoryQueryTool(Tool):
    """Tool for querying conversation memory.

    Allows the agent to search and retrieve past conversation context,
    user preferences, and stored information.
    """

    name = "memory_query"
    description = "Query conversation memory and user information"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters={
                "operation": {
                    "type": "string",
                    "enum": ["recent", "search", "user_info"],
                    "description": "Type of memory operation",
                },
                "query": {
                    "type": "string",
                    "description": "Search query for 'search' operation",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results",
                    "default": 5,
                },
            },
            required=["operation"],
            category=ToolCategory.READ_ONLY,
            risk_level=ToolRiskLevel.LOW,
            examples=[
                {"operation": "recent", "limit": 3},
                {"operation": "search", "query": "Python programming"},
                {"operation": "user_info"},
            ],
        )

    async def execute(self, context: ToolContext, **params) -> ToolResult:
        operation = params["operation"]
        query = params.get("query")
        limit = params.get("limit", 5)

        if not context.memory_store:
            return ToolResult.error_result("Memory store not configured")

        try:
            if operation == "recent":
                memories = await context.memory_store.retrieve_recent(
                    session_id=context.session_id,
                    limit=limit,
                )
                return ToolResult.success_result(
                    {
                        "memories": [
                            {
                                "user": m.user_message,
                                "assistant": m.assistant_message,
                                "timestamp": (
                                    m.timestamp.isoformat() if hasattr(m, "timestamp") else None
                                ),
                            }
                            for m in memories
                        ],
                    }
                )

            elif operation == "search":
                if not query:
                    return ToolResult.error_result("Query required for search operation")

                memories = await context.memory_store.retrieve_relevant(
                    query=query,
                    session_id=context.session_id,
                    limit=limit,
                )
                return ToolResult.success_result(
                    {
                        "query": query,
                        "memories": memories,
                    }
                )

            elif operation == "user_info":
                # Return user-related information
                return ToolResult.success_result(
                    {
                        "user_id": context.user_id,
                        "session_id": context.session_id,
                    }
                )

            else:
                return ToolResult.error_result(f"Unknown operation: {operation}")

        except (ValueError, RuntimeError) as e:
            return ToolResult.error_result(f"Memory query failed: {e}")
