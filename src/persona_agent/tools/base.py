"""Base classes and interfaces for the tool system.

This module defines the foundational abstractions for all tools,
including the base Tool class, execution context, and result types.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class ToolCategory(Enum):
    """Categories of tools based on their function and risk level."""

    READ_ONLY = auto()  # Safe, read-only operations
    FILE_SYSTEM = auto()  # File read/write operations
    NETWORK = auto()  # Network/API operations
    CODE_EXECUTION = auto()  # Code execution (high risk)
    SYSTEM = auto()  # System-level operations (highest risk)


class ToolRiskLevel(Enum):
    """Risk levels for tool execution."""

    LOW = "low"  # Read-only, no side effects
    MEDIUM = "medium"  # Local changes, limited scope
    HIGH = "high"  # External calls, persistent changes
    CRITICAL = "critical"  # Code execution, system access


@dataclass
class ToolSchema:
    """Schema definition for tool parameters.

    Defines the structure and validation rules for tool inputs,
    compatible with JSON Schema and OpenAI function calling format.

    Attributes:
        name: Tool name
        description: Human-readable description
        parameters: JSON Schema for parameters
        required: List of required parameter names
        category: Tool category for permission management
        risk_level: Risk level for security policies
    """

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    required: list[str] = field(default_factory=list)
    category: ToolCategory = ToolCategory.READ_ONLY
    risk_level: ToolRiskLevel = ToolRiskLevel.LOW
    examples: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert schema to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "required": self.required,
            "category": self.category.name,
            "risk_level": self.risk_level.value,
            "examples": self.examples,
        }

    def to_json_schema(self) -> dict[str, Any]:
        """Convert to OpenAI-compatible function schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required,
                },
            },
        }

    def to_anthropic_schema(self) -> dict[str, Any]:
        """Convert to Anthropic-compatible tool schema."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": self.parameters,
                "required": self.required,
            },
        }


@dataclass
class ToolContext:
    """Context passed to tools during execution.

    Contains information about the execution environment, user,
    and session that tools may need to perform their functions.

    Attributes:
        session_id: Unique session identifier
        user_id: User identifier (if authenticated)
        working_directory: Current working directory for file operations
        environment: Environment variables available to the tool
        metadata: Additional context metadata
        permission_level: Current permission level for this session
        permissions: List of specific permissions granted
    """

    session_id: str = "default"
    user_id: str | None = None
    working_directory: str = "."
    environment: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    permission_level: str = "standard"
    memory_store: Any | None = None
    permissions: list[str] = field(default_factory=list)

    def has_permission(self, required_level: str) -> bool:
        """Check if context has required permission level."""
        levels = ["restricted", "standard", "elevated", "admin"]
        try:
            return levels.index(self.permission_level) >= levels.index(required_level)
        except ValueError:
            return False


@dataclass
class ToolResult:
    """Result returned from tool execution.

    Attributes:
        success: Whether execution succeeded
        data: Result data (any serializable type)
        error: Error message if failed
        execution_time_ms: Time taken to execute
        metadata: Additional execution metadata
    """

    success: bool
    data: Any = None
    error: str | None = None
    execution_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata,
        }

    @classmethod
    def success_result(
        cls,
        data: Any,
        execution_time_ms: float = 0.0,
        **metadata: Any,
    ) -> ToolResult:
        """Create a successful result."""
        return cls(
            success=True,
            data=data,
            execution_time_ms=execution_time_ms,
            metadata=metadata,
        )

    @classmethod
    def error_result(
        cls,
        error: str,
        execution_time_ms: float = 0.0,
        **metadata: Any,
    ) -> ToolResult:
        """Create an error result."""
        return cls(
            success=False,
            error=error,
            execution_time_ms=execution_time_ms,
            metadata=metadata,
        )


class Tool(ABC):
    """Abstract base class for all tools.

    Tools are modular capabilities that can be discovered and executed
    by the agent. Each tool defines its schema, validation logic, and
    execution behavior.

    Example:
        class CalculatorTool(Tool):
            name = "calculator"
            description = "Perform mathematical calculations"

            def get_schema(self) -> ToolSchema:
                return ToolSchema(
                    name=self.name,
                    description=self.description,
                    parameters={
                        "expression": {
                            "type": "string",
                            "description": "Math expression to evaluate",
                        }
                    },
                    required=["expression"],
                    category=ToolCategory.READ_ONLY,
                    risk_level=ToolRiskLevel.LOW,
                )

            async def execute(self, context: ToolContext, **params) -> ToolResult:
                try:
                    result = eval(params["expression"])
                    return ToolResult.success_result(result)
                except Exception as e:
                    return ToolResult.error_result(str(e))
    """

    # Class attributes (must be defined by subclasses)
    name: str = ""
    description: str = ""
    version: str = "1.0.0"

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize tool with optional configuration.

        Args:
            config: Tool-specific configuration

        Raises:
            ValueError: If tool name or description is not set
        """
        if not self.name:
            raise ValueError("Tool must have a name")
        if not self.description:
            raise ValueError("Tool must have a description")

        self.config = config or {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the tool.

        Called once when the tool is first loaded. Override to set up
        resources, load models, connect to APIs, etc.
        """
        self._initialized = True

    async def cleanup(self) -> None:
        """Cleanup resources when tool is unloaded."""
        self._initialized = False

    @abstractmethod
    def get_schema(self) -> ToolSchema:
        """Get the tool's schema definition.

        Returns:
            ToolSchema with parameter definitions and metadata
        """
        pass

    @abstractmethod
    async def execute(self, context: ToolContext, **params: Any) -> ToolResult:
        """Execute the tool with given parameters.

        Args:
            context: Execution context with environment info
            **params: Validated parameters from the schema

        Returns:
            ToolResult with execution outcome
        """
        pass

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, str | None]:
        """Validate parameters against the tool schema.

        Args:
            params: Parameters to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        schema = self.get_schema()

        # Check required parameters
        for required in schema.required:
            if required not in params:
                return False, f"Missing required parameter: {required}"

        # Basic type checking
        for param_name, param_value in params.items():
            if param_name in schema.parameters:
                expected_type = schema.parameters[param_name].get("type")
                if expected_type and not self._check_type(param_value, expected_type):
                    return False, f"Parameter '{param_name}' has wrong type"

        return True, None

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected type."""

        type_map: dict[str, type | tuple[type, ...]] = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        if expected_type not in type_map:
            return True  # Unknown type, allow

        expected = type_map[expected_type]
        return isinstance(value, expected)

    async def run(
        self,
        context: ToolContext,
        **params: Any,
    ) -> ToolResult:
        """Run the tool with validation and timing.

        This is the main entry point for tool execution. It handles
        validation, timing, and error handling.

        Args:
            context: Execution context
            **params: Tool parameters

        Returns:
            ToolResult with execution outcome
        """
        start_time = time.time()

        # Validate parameters
        is_valid, error = self.validate_params(params)
        if not is_valid:
            return ToolResult.error_result(
                error or "Validation failed",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # Check permissions
        schema = self.get_schema()
        permission_map = {
            ToolRiskLevel.LOW: "restricted",
            ToolRiskLevel.MEDIUM: "standard",
            ToolRiskLevel.HIGH: "elevated",
            ToolRiskLevel.CRITICAL: "admin",
        }
        required_permission = permission_map.get(schema.risk_level, "standard")

        if not context.has_permission(required_permission):
            return ToolResult.error_result(
                f"Insufficient permissions for tool '{self.name}'. "
                f"Required: {required_permission}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # Execute
        try:
            result = await self.execute(context, **params)
            result.execution_time_ms = (time.time() - start_time) * 1000
            return result
        except Exception as e:
            return ToolResult.error_result(
                f"Execution error: {e}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )


# Convenience decorator for simple tools
def tool(
    name: str,
    description: str,
    category: ToolCategory = ToolCategory.READ_ONLY,
    risk_level: ToolRiskLevel = ToolRiskLevel.LOW,
) -> Callable[[Callable], Callable]:
    """Decorator to create a Tool class from a function.

    Example:
        @tool(name="greet", description="Greet someone")
        async def greet_tool(context: ToolContext, name: str) -> ToolResult:
            return ToolResult.success_result(f"Hello, {name}!")
    """

    def decorator(func: Callable) -> Callable:
        class FunctionTool(Tool):
            _func = staticmethod(func)

            def get_schema(self) -> ToolSchema:
                import inspect

                sig = inspect.signature(func)

                # Build parameters from function signature
                parameters = {}
                required = []
                for param_name, param in sig.parameters.items():
                    if param_name == "context":
                        continue

                    param_info = {"type": "string"}
                    if param.default is not param.empty:
                        param_info["default"] = param.default
                    else:
                        required.append(param_name)

                    parameters[param_name] = param_info

                return ToolSchema(
                    name=name,
                    description=description,
                    parameters=parameters,
                    required=required,
                    category=category,
                    risk_level=risk_level,
                )

            async def execute(self, context: ToolContext, **params) -> ToolResult:
                return await func(context, **params)

        FunctionTool.__name__ = f"{name.title()}Tool"
        FunctionTool.name = name
        FunctionTool.description = description

        # Return a wrapper that has _tool_class attribute
        from typing import Protocol

        class ToolWrapper(Protocol):
            _tool_class: type[Tool]
            __name__: str
            __doc__: str | None
            __call__: Callable

        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper._tool_class = FunctionTool  # type: ignore[attr-defined]
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator
