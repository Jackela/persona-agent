"""Tool execution with security policy enforcement.

Provides controlled execution of tools with permission checks,
rate limiting, and audit logging.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from persona_agent.tools.base import Tool, ToolCategory, ToolContext, ToolResult, ToolRiskLevel

logger = logging.getLogger(__name__)


@dataclass
class SecurityPolicy:
    """Security policy for tool execution.

    Defines what tools are allowed, risk limits, and permission requirements.
    """

    # Allowed tool categories
    allowed_categories: set[ToolCategory] = field(default_factory=lambda: {
        ToolCategory.READ_ONLY,
        ToolCategory.FILE_SYSTEM,
        ToolCategory.NETWORK,
    })

    # Maximum risk level allowed
    max_risk_level: ToolRiskLevel = ToolRiskLevel.HIGH

    # Required permissions for different risk levels
    required_permissions: dict[ToolRiskLevel, list[str]] = field(default_factory=dict)

    # Rate limits (calls per minute)
    rate_limits: dict[str, int] = field(default_factory=lambda: {
        "default": 60,
        "network": 10,
        "code_execution": 5,
    })

    # Blocked tools (by name)
    blocked_tools: set[str] = field(default_factory=set)

    def __post_init__(self):
        """Set default required permissions."""
        if not self.required_permissions:
            self.required_permissions = {
                ToolRiskLevel.LOW: [],
                ToolRiskLevel.MEDIUM: ["medium_risk"],
                ToolRiskLevel.HIGH: ["high_risk"],
                ToolRiskLevel.CRITICAL: ["critical_risk"],
            }

    def is_tool_allowed(self, tool: Tool, tool_schema: Any) -> tuple[bool, str | None]:
        """Check if a tool is allowed by this policy.

        Args:
            tool: Tool instance
            tool_schema: Tool schema

        Returns:
            (allowed, reason) tuple
        """
        # Check if tool is explicitly blocked
        if tool.name in self.blocked_tools:
            return False, f"Tool '{tool.name}' is blocked"

        # Check category
        if tool_schema.category not in self.allowed_categories:
            return False, f"Category '{tool_schema.category.name}' not allowed"

        # Check risk level
        risk_order = {
            ToolRiskLevel.LOW: 0,
            ToolRiskLevel.MEDIUM: 1,
            ToolRiskLevel.HIGH: 2,
            ToolRiskLevel.CRITICAL: 3,
        }
        tool_risk = risk_order.get(tool_schema.risk_level, 3)
        max_risk = risk_order.get(self.max_risk_level, 3)

        if tool_risk > max_risk:
            return False, f"Risk level '{tool_schema.risk_level.value}' exceeds maximum"

        return True, None

    def check_permissions(self, tool_schema: Any, user_permissions: list[str]) -> tuple[bool, str | None]:
        """Check if user has required permissions for a tool.

        Args:
            tool_schema: Tool schema
            user_permissions: User's granted permissions

        Returns:
            (has_permission, missing_permission) tuple
        """
        required = self.required_permissions.get(tool_schema.risk_level, [])

        for perm in required:
            if perm not in user_permissions:
                return False, perm

        return True, None


class ToolExecutor:
    """Executor for tools with security policy enforcement.

    Handles:
    - Permission checking
    - Rate limiting
    - Audit logging
    - Error handling
    """

    def __init__(
        self,
        policy: SecurityPolicy | None = None,
        enable_audit_log: bool = True,
    ):
        """Initialize tool executor.

        Args:
            policy: Security policy to enforce
            enable_audit_log: Whether to enable audit logging
        """
        self.policy = policy or SecurityPolicy()
        self.enable_audit_log = enable_audit_log
        self._call_counts: dict[str, int] = {}

    async def execute(
        self,
        tool: Tool,
        context: ToolContext,
        **params,
    ) -> ToolResult:
        """Execute a tool with security checks.

        Args:
            tool: Tool to execute
            context: Tool execution context
            **params: Tool parameters

        Returns:
            Tool execution result
        """
        schema = tool.get_schema()

        # Check if tool is allowed
        allowed, reason = self.policy.is_tool_allowed(tool, schema)
        if not allowed:
            logger.warning(f"Tool '{tool.name}' blocked by policy: {reason}")
            return ToolResult.error_result(f"Tool not allowed: {reason}")

        # Check permissions
        has_perm, missing = self.policy.check_permissions(schema, context.permissions)
        if not has_perm:
            logger.warning(f"Missing permission '{missing}' for tool '{tool.name}'")
            return ToolResult.error_result(f"Missing required permission: {missing}")

        # Check rate limit
        if not self._check_rate_limit(tool):
            return ToolResult.error_result("Rate limit exceeded")

        # Log execution
        if self.enable_audit_log:
            self._log_execution(tool.name, params, context)

        try:
            # Execute tool
            result = await tool.execute(context, **params)

            # Log result
            if self.enable_audit_log:
                self._log_result(tool.name, result)

            return result

        except Exception as e:
            logger.exception(f"Tool execution failed: {tool.name}")
            return ToolResult.error_result(f"Execution failed: {e}")

    def _check_rate_limit(self, tool: Tool) -> bool:
        """Check if tool execution is within rate limits.

        Args:
            tool: Tool to check

        Returns:
            True if within limits
        """
        # Get limit for this tool category
        limit = self.policy.rate_limits.get("default", 60)

        schema = tool.get_schema()
        if schema.category == ToolCategory.NETWORK:
            limit = self.policy.rate_limits.get("network", 10)
        elif schema.category == ToolCategory.CODE_EXECUTION:
            limit = self.policy.rate_limits.get("code_execution", 5)

        # Check current count
        current = self._call_counts.get(tool.name, 0)
        if current >= limit:
            return False

        # Increment count
        self._call_counts[tool.name] = current + 1
        return True

    def _log_execution(self, tool_name: str, params: dict, context: ToolContext) -> None:
        """Log tool execution for audit.

        Args:
            tool_name: Name of tool being executed
            params: Tool parameters
            context: Execution context
        """
        logger.info(
            f"Tool execution: {tool_name} by user={context.user_id} "
            f"session={context.session_id} params={list(params.keys())}"
        )

    def _log_result(self, tool_name: str, result: ToolResult) -> None:
        """Log tool execution result.

        Args:
            tool_name: Name of tool
            result: Execution result
        """
        if result.success:
            logger.info(f"Tool {tool_name} succeeded")
        else:
            logger.warning(f"Tool {tool_name} failed: {result.error}")

    def reset_rate_limits(self) -> None:
        """Reset all rate limit counters."""
        self._call_counts.clear()
