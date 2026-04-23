"""Security sandbox for safe code execution.

This module provides sandboxed execution environments with:
- Resource limits (CPU time, memory)
- Restricted Python execution
- Timeout controls
- Permission-based access control
"""

from __future__ import annotations

import ast
import contextlib
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Any


@dataclass
class SandboxConfig:
    """Configuration for sandbox execution."""

    # Time limits
    timeout_seconds: float = 30.0
    cpu_time_limit_seconds: int = 10

    # Memory limits
    max_memory_mb: int = 128

    # File system
    allowed_paths: list[str] | None = None
    temp_dir: str | None = None

    # Network
    allow_network: bool = False

    # Python execution
    allowed_modules: list[str] | None = None
    blocked_builtins: list[str] | None = None

    def __post_init__(self):
        if self.allowed_modules is None:
            self.allowed_modules = [
                "math",
                "random",
                "statistics",
                "datetime",
                "itertools",
                "collections",
                "functools",
                "operator",
                "json",
                "re",
                "string",
                "hashlib",
                "base64",
                "typing",
                "decimal",
                "fractions",
                "numbers",
                "inspect",
                "types",
                "copy",
            ]

        if self.blocked_builtins is None:
            self.blocked_builtins = [
                "__import__",
                "eval",
                "exec",
                "compile",
                "open",
                "input",
                "raw_input",
                "exit",
                "quit",
                "help",
                "reload",
                "breakpoint",
            ]


class SecurityError(Exception):
    """Raised when security policy is violated."""

    pass


class TimeoutError(Exception):
    """Raised when execution times out."""

    pass


class MemoryLimitError(Exception):
    """Raised when memory limit is exceeded."""

    pass


class RestrictedPythonExecutor:
    """Execute Python code in a restricted environment.

    This executor provides a safer alternative to eval/exec by:
    1. AST validation to block dangerous constructs
    2. Restricted builtins
    3. Limited module imports
    """

    DANGEROUS_NODES = (
        ast.Import,
        ast.ImportFrom,
        ast.Call,
        ast.Subscript,
        ast.Attribute,
    )

    def __init__(self, config: SandboxConfig | None = None):
        self.config = config or SandboxConfig()
        self._setup_restricted_globals()

    def _setup_restricted_globals(self):
        """Setup restricted global namespace."""
        # Start with empty builtins
        safe_builtins = {
            "True": True,
            "False": False,
            "None": None,
            "abs": abs,
            "all": all,
            "any": any,
            "bin": bin,
            "bool": bool,
            "chr": chr,
            "dict": dict,
            "dir": dir,
            "divmod": divmod,
            "enumerate": enumerate,
            "filter": filter,
            "float": float,
            "format": format,
            "frozenset": frozenset,
            "hasattr": hasattr,
            "hash": hash,
            "hex": hex,
            "id": id,
            "int": int,
            "isinstance": isinstance,
            "issubclass": issubclass,
            "iter": iter,
            "len": len,
            "list": list,
            "map": map,
            "max": max,
            "min": min,
            "next": next,
            "oct": oct,
            "ord": ord,
            "pow": pow,
            "print": print,
            "range": range,
            "repr": repr,
            "reversed": reversed,
            "round": round,
            "set": set,
            "slice": slice,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "type": type,
            "vars": vars,
            "zip": zip,
        }

        # Create restricted __import__ function
        allowed_modules = set(self.config.allowed_modules or [])

        def restricted_import(name, *args, **kwargs):
            # Get the top-level module name
            module_name = name.split(".")[0]
            if module_name not in allowed_modules:
                raise ImportError(f"Import of '{module_name}' not allowed")
            return __import__(name, *args, **kwargs)

        # Setup globals with restricted builtins
        self.globals = {
            "__builtins__": {
                **safe_builtins,
                "__import__": restricted_import,
            },
        }

        # Pre-load allowed modules
        for module_name in allowed_modules:
            try:
                module = __import__(module_name)
                self.globals[module_name] = module
            except ImportError:
                pass

    def _validate_ast(self, tree: ast.AST) -> tuple[bool, str | None]:
        """Validate AST for dangerous constructs."""
        allowed_modules = set(self.config.allowed_modules or [])

        for node in ast.walk(tree):
            # Check for imports
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module not in allowed_modules:
                        return False, f"Import of '{node.module}' not allowed"
                elif isinstance(node, ast.Import):
                    # Check all names in the import
                    for alias in node.names:
                        module_name = alias.name.split(".")[0]  # Get top-level module
                        if module_name not in allowed_modules:
                            return False, f"Import of '{module_name}' not allowed"
                else:
                    return False, "Dynamic imports not allowed"

            # Check for dangerous calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in (self.config.blocked_builtins or []):
                        return False, f"Call to '{node.func.id}' not allowed"

            # Check for attribute access on restricted objects
            if isinstance(node, ast.Attribute):
                if node.attr.startswith("_"):
                    return False, f"Access to private attribute '{node.attr}' not allowed"

        return True, None

    def execute(self, code: str, locals_dict: dict | None = None) -> dict[str, Any]:
        """Execute code in restricted environment.

        Args:
            code: Python code to execute
            locals_dict: Local variables

        Returns:
            Dictionary with execution results
        """
        try:
            # Parse and validate
            tree = ast.parse(code, mode="exec")
            is_valid, error = self._validate_ast(tree)

            if not is_valid:
                return {
                    "success": False,
                    "error": f"Security violation: {error}",
                    "output": "",
                }

            # Compile and execute
            compiled = compile(tree, "<sandbox>", "exec")
            exec_locals = locals_dict or {}

            # Capture output
            import io

            stdout = io.StringIO()
            stderr = io.StringIO()

            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exec(compiled, self.globals, exec_locals)  # nosec B102

            return {
                "success": True,
                "output": stdout.getvalue(),
                "error_output": stderr.getvalue(),
                "locals": {k: v for k, v in exec_locals.items() if not k.startswith("_")},
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "output": "",
            }


class ProcessSandbox:
    """Sandbox using separate process with resource limits.

    Provides maximum isolation by running code in a subprocess
    with strict resource limits enforced by the OS.
    """

    def __init__(self, config: SandboxConfig | None = None):
        self.config = config or SandboxConfig()

    def execute(
        self,
        code: str,
        language: str = "python",
    ) -> dict[str, Any]:
        """Execute code in isolated subprocess.

        Args:
            code: Code to execute
            language: Programming language (python, bash)

        Returns:
            Execution results
        """
        if language == "python":
            return self._execute_python(code)
        elif language == "bash":
            return self._execute_bash(code)
        else:
            return {"success": False, "error": f"Unsupported language: {language}"}

    def _execute_python(self, code: str) -> dict[str, Any]:
        """Execute Python code in subprocess."""
        # Escape triple quotes in user code
        escaped_code = code.replace('"""', '\\"""')

        # Build wrapper script using string concatenation to avoid f-string issues
        wrapper_parts = [
            "import sys",
            "import resource",
            "",
            "# Set resource limits",
            "def set_limits():",
            f"    resource.setrlimit(resource.RLIMIT_CPU, ({self.config.cpu_time_limit_seconds}, {self.config.cpu_time_limit_seconds}))",
            f"    max_bytes = {self.config.max_memory_mb} * 1024 * 1024",
            "    resource.setrlimit(resource.RLIMIT_AS, (max_bytes, max_bytes))",
            "    resource.setrlimit(resource.RLIMIT_FSIZE, (10*1024*1024, 10*1024*1024))",
            "",
            "set_limits()",
            "",
            "# Execute user code",
            f'code = """{escaped_code}"""',
            "",
            "# Restricted exec",
            'globals_dict = {"__builtins__": {}}',
            "locals_dict = {}",
            "",
            "# Add safe builtins",
            "safe_builtins = [",
            '    "True", "False", "None",',
            '    "abs", "all", "any", "bin", "bool", "chr", "dict", "dir",',
            '    "divmod", "enumerate", "filter", "float", "format", "frozenset",',
            '    "hasattr", "hash", "hex", "id", "int", "isinstance", "issubclass",',
            '    "iter", "len", "list", "map", "max", "min", "next", "oct", "ord",',
            '    "pow", "print", "range", "repr", "reversed", "round", "set", "slice",',
            '    "sorted", "str", "sum", "tuple", "type", "vars", "zip",',
            "]",
            "for name in safe_builtins:",
            "    if name in __builtins__:",
            '        globals_dict["__builtins__"][name] = __builtins__[name]',
            "",
            "# Add allowed modules",
            f"allowed_modules = {self.config.allowed_modules!r}",
            "for mod_name in allowed_modules:",
            "    try:",
            "        mod = __import__(mod_name)",
            "        globals_dict[mod_name] = mod",
            "    except Exception:",
            "        pass",
            "",
            "try:",
            "    exec(code, globals_dict, locals_dict)",
            "except Exception as e:",
            '    print(f"Error: {e}", file=sys.stderr)',
            "    sys.exit(1)",
        ]
        wrapper = "\n".join(wrapper_parts)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(wrapper)
            script_path = f.name

        try:
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds,
            )

            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None,
                "exit_code": result.returncode,
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Execution timed out after {self.config.timeout_seconds}s",
                "output": "",
            }

        finally:
            with contextlib.suppress(Exception):
                os.unlink(script_path)

    def _execute_bash(self, command: str) -> dict[str, Any]:
        """Execute bash command with restrictions."""
        # Block dangerous commands
        dangerous_patterns = [
            "rm -rf /",
            "rm -rf /*",
            ":(){ :|:& };:",
            "> /dev/sda",
            "mkfs",
            "dd if=/dev/zero",
            "curl | sh",
            "wget | sh",
        ]

        for pattern in dangerous_patterns:
            if pattern in command.lower():
                return {
                    "success": False,
                    "error": f"Dangerous command pattern detected: {pattern}",
                }

        try:
            result = subprocess.run(
                ["bash", "-c", command],
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds,
                cwd=self.config.temp_dir or ".",
            )

            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None,
                "exit_code": result.returncode,
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Command timed out after {self.config.timeout_seconds}s",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
