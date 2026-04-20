"""Code execution tool with security sandbox.

Provides safe execution of Python and shell code with resource limits
and security restrictions.
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
from persona_agent.tools.sandbox import ProcessSandbox, RestrictedPythonExecutor, SandboxConfig


class CodeExecutionTool(Tool):
    """Tool for executing code in a secure sandbox.

    Supports Python and shell execution with:
    - Resource limits (CPU time, memory)
    - Restricted Python execution
    - Timeout controls
    - Permission-based access control
    """

    name = "code_execute"
    description = "Execute Python or shell code in a secure sandbox"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.sandbox_config = self._build_sandbox_config(config or {})
        self.sandbox = ProcessSandbox(self.sandbox_config)
        self.restricted_executor = RestrictedPythonExecutor(self.sandbox_config)

    def _build_sandbox_config(self, config: dict) -> SandboxConfig:
        """Build sandbox configuration from tool config."""
        return SandboxConfig(
            timeout_seconds=config.get("timeout_seconds", 30.0),
            cpu_time_limit_seconds=config.get("cpu_time_limit_seconds", 10.0),
            max_memory_mb=config.get("max_memory_mb", 128),
            allowed_modules=config.get("allowed_modules"),
            allow_network=config.get("allow_network", False),
            temp_dir=config.get("temp_dir"),
        )

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters={
                "code": {
                    "type": "string",
                    "description": "Code to execute",
                },
                "language": {
                    "type": "string",
                    "enum": ["python", "bash"],
                    "description": "Programming language",
                    "default": "python",
                },
                "mode": {
                    "type": "string",
                    "enum": ["restricted", "sandboxed"],
                    "description": "Execution mode: 'restricted' for in-process (Python only), 'sandboxed' for subprocess isolation",
                    "default": "sandboxed",
                },
            },
            required=["code"],
            category=ToolCategory.CODE_EXECUTION,
            risk_level=ToolRiskLevel.CRITICAL,
            examples=[
                {
                    "code": "print('Hello, World!')",
                    "language": "python",
                },
                {
                    "code": "result = [x**2 for x in range(10)]\nprint(result)",
                    "language": "python",
                    "mode": "restricted",
                },
                {
                    "code": "ls -la",
                    "language": "bash",
                },
            ],
        )

    async def execute(self, context: ToolContext, **params) -> ToolResult:
        code = params["code"]
        language = params.get("language", "python")
        mode = params.get("mode", "sandboxed")

        # Validate code length
        max_code_length = 10000
        if len(code) > max_code_length:
            return ToolResult.error_result(
                f"Code too long: {len(code)} characters (max: {max_code_length})"
            )

        # Execute based on mode
        if language == "python" and mode == "restricted":
            # Use in-process restricted executor for faster execution
            result = self.restricted_executor.execute(code)
            return ToolResult.success_result(
                {
                    "language": "python",
                    "mode": "restricted",
                    "output": result.get("output", ""),
                    "error_output": result.get("error_output", ""),
                    "error": result.get("error"),
                    "success": result.get("success", False),
                }
            )
        else:
            # Use subprocess sandbox for maximum isolation
            result = self.sandbox.execute(code, language=language)
            return ToolResult.success_result(
                {
                    "language": language,
                    "mode": "sandboxed",
                    "output": result.get("output", ""),
                    "error": result.get("error"),
                    "exit_code": result.get("exit_code", 0),
                    "success": result.get("success", False),
                }
            )
