"""Tests for security sandbox."""

import pytest

from persona_agent.tools.sandbox import (
    RestrictedPythonExecutor,
    SandboxConfig,
)


class TestSandboxConfig:
    """Tests for SandboxConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = SandboxConfig()

        assert config.timeout_seconds == 30.0
        assert config.max_memory_mb == 128
        assert config.allow_network is False
        assert config.allowed_modules is not None
        assert "math" in config.allowed_modules
        assert "json" in config.allowed_modules

    def test_custom_config(self):
        """Test custom configuration."""
        config = SandboxConfig(
            timeout_seconds=60.0,
            max_memory_mb=256,
            allow_network=True,
            allowed_modules=["math", "random"],
        )

        assert config.timeout_seconds == 60.0
        assert config.max_memory_mb == 256
        assert config.allow_network is True
        assert config.allowed_modules == ["math", "random"]


class TestRestrictedPythonExecutor:
    """Tests for RestrictedPythonExecutor."""

    @pytest.fixture
    def executor(self):
        return RestrictedPythonExecutor()

    def test_execute_simple_code(self, executor):
        """Test executing simple Python code."""
        result = executor.execute("x = 1 + 1\nprint(x)")

        assert result["success"] is True
        assert "2" in result["output"]

    def test_execute_math_operations(self, executor):
        """Test executing math operations."""
        result = executor.execute("""
import math
result = math.sqrt(16)
print(result)
""")

        assert result["success"] is True
        assert "4.0" in result["output"]

    def test_blocked_import(self, executor):
        """Test that disallowed imports are blocked."""
        result = executor.execute("import os\nprint(os.getcwd())")

        assert result["success"] is False
        assert "not allowed" in result["error"].lower()

    def test_blocked_builtin(self, executor):
        """Test that dangerous builtins are blocked."""
        result = executor.execute("eval('1 + 1')")

        assert result["success"] is False
        assert "not allowed" in result["error"].lower()

    def test_blocked_private_access(self, executor):
        """Test that private attribute access is blocked."""
        result = executor.execute("""
class Test:
    def __init__(self):
        self._private = 1
t = Test()
print(t._private)
""")

        assert result["success"] is False
        assert "private" in result["error"].lower()

    def test_return_locals(self, executor):
        """Test that local variables are returned."""
        result = executor.execute("x = 42\ny = 'hello'")

        assert result["success"] is True
        assert result["locals"]["x"] == 42
        assert result["locals"]["y"] == "hello"

    def test_syntax_error(self, executor):
        """Test handling of syntax errors."""
        result = executor.execute("if x")  # Incomplete statement

        assert result["success"] is False
        assert result["error"] is not None

    def test_runtime_error(self, executor):
        """Test handling of runtime errors."""
        result = executor.execute("1 / 0")

        assert result["success"] is False
        assert "division by zero" in result["error"].lower()


class TestSandboxSecurity:
    """Security-focused tests for the sandbox."""

    @pytest.fixture
    def executor(self):
        config = SandboxConfig()
        return RestrictedPythonExecutor(config)

    def test_no_file_access(self, executor):
        """Test that file access is blocked."""
        result = executor.execute("""
with open('/etc/passwd', 'r') as f:
    print(f.read())
""")

        assert result["success"] is False

    def test_no_importlib(self, executor):
        """Test that importlib is blocked."""
        result = executor.execute("""
import importlib
os = importlib.import_module('os')
""")

        assert result["success"] is False

    def test_no_subprocess(self, executor):
        """Test that subprocess is blocked."""
        result = executor.execute("""
import subprocess
subprocess.run(['ls', '-la'])
""")

        assert result["success"] is False

    def test_safe_operations(self, executor):
        """Test that safe operations work."""
        code = """
# List operations
numbers = [1, 2, 3, 4, 5]
squared = [x**2 for x in numbers]
print(squared)

# Dict operations
data = {"a": 1, "b": 2}
print(data.get("a"))

# String operations
text = "Hello, World!"
print(text.upper())
"""
        result = executor.execute(code)

        assert result["success"] is True


class TestSandboxEdgeCases:
    """Edge case tests for sandbox."""

    @pytest.fixture
    def executor(self):
        return RestrictedPythonExecutor()

    def test_empty_code(self, executor):
        """Test executing empty code."""
        result = executor.execute("")

        # Empty code should succeed with no output
        assert result["success"] is True

    def test_whitespace_only(self, executor):
        """Test executing whitespace-only code."""
        result = executor.execute("   \n\n   ")

        assert result["success"] is True

    def test_very_long_output(self, executor):
        """Test handling of very long output."""
        code = "print('x' * 10000)"
        result = executor.execute(code)

        assert result["success"] is True
        assert len(result["output"]) == 10001  # 10000 chars + newline

    def test_unicode_in_code(self, executor):
        """Test handling unicode in code."""
        code = """
emoji = "🎉"
chinese = "你好"
print(emoji, chinese)
"""
        result = executor.execute(code)

        assert result["success"] is True
        assert "🎉" in result["output"]
        assert "你好" in result["output"]
