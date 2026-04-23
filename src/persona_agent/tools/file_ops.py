"""File operation tools for reading, writing, and listing files.

These tools provide safe file system access with path validation,
size limits, and permission checks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from persona_agent.tools.base import (
    Tool,
    ToolCategory,
    ToolContext,
    ToolResult,
    ToolRiskLevel,
    ToolSchema,
)


class FileReadTool(Tool):
    """Tool for reading file contents.

    Safely reads files with path validation and size limits.
    Supports text and binary file detection.
    """

    name = "file_read"
    description = "Read the contents of a file"

    DEFAULT_MAX_SIZE = 1024 * 1024  # 1MB default limit
    ALLOWED_EXTENSIONS = {
        # Text files
        ".txt",
        ".md",
        ".json",
        ".yaml",
        ".yml",
        ".xml",
        ".csv",
        # Code files
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".html",
        ".css",
        ".java",
        ".c",
        ".cpp",
        ".h",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".sh",
        ".bash",
        ".zsh",
        ".ps1",
        ".bat",
        # Config files
        ".conf",
        ".cfg",
        ".ini",
        ".toml",
        ".properties",
        # Data files
        ".sql",
        ".log",
        ".svg",
    }

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.max_size = (
            config.get("max_size", self.DEFAULT_MAX_SIZE) if config else self.DEFAULT_MAX_SIZE
        )
        self.allowed_extensions = (
            set(config.get("allowed_extensions", self.ALLOWED_EXTENSIONS))
            if config
            else self.ALLOWED_EXTENSIONS
        )

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters={
                "path": {
                    "type": "string",
                    "description": "Path to the file to read (relative to working directory)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to read (0 = all)",
                    "default": 0,
                },
                "offset": {
                    "type": "integer",
                    "description": "Line offset to start reading from",
                    "default": 0,
                },
            },
            required=["path"],
            category=ToolCategory.FILE_SYSTEM,
            risk_level=ToolRiskLevel.LOW,
            examples=[
                {"path": "README.md"},
                {"path": "src/main.py", "limit": 50},
                {"path": "data/config.yaml", "offset": 10, "limit": 20},
            ],
        )

    async def execute(self, context: ToolContext, **params) -> ToolResult:
        file_path = params["path"]
        limit = params.get("limit", 0)
        offset = params.get("offset", 0)

        # Resolve path relative to working directory
        resolved_path = self._resolve_path(file_path, context.working_directory)

        # Validate path is within bounds
        is_valid, error = self._validate_path(resolved_path, context.working_directory)
        if not is_valid:
            return ToolResult.error_result(error or "Path validation failed")

        # Check file exists
        if not resolved_path.exists():
            return ToolResult.error_result(f"File not found: {file_path}")

        if not resolved_path.is_file():
            return ToolResult.error_result(f"Path is not a file: {file_path}")

        # Check extension
        if resolved_path.suffix not in self.allowed_extensions:
            return ToolResult.error_result(
                f"File type '{resolved_path.suffix}' not allowed. "
                f"Allowed: {', '.join(sorted(self.allowed_extensions)[:10])}..."
            )

        # Check size
        try:
            file_size = resolved_path.stat().st_size
            if file_size > self.max_size:
                return ToolResult.error_result(
                    f"File too large: {file_size} bytes (max: {self.max_size})"
                )
        except OSError as e:
            return ToolResult.error_result(f"Cannot access file: {e}")

        # Read file
        try:
            # Try to read as text
            try:
                content = resolved_path.read_text(encoding="utf-8")
                is_binary = False
            except UnicodeDecodeError:
                # Binary file - read limited bytes
                content = resolved_path.read_bytes()[:1024].hex()
                is_binary = True

            # Apply line limits
            if not is_binary and (limit > 0 or offset > 0):
                lines = content.split("\n")
                if offset > 0:
                    lines = lines[offset:]
                if limit > 0:
                    lines = lines[:limit]
                content = "\n".join(lines)
                total_lines = len(content.split("\n")) if content else 0
            else:
                total_lines = len(content.split("\n")) if not is_binary else 0

            return ToolResult.success_result(
                {
                    "content": content,
                    "path": str(resolved_path),
                    "size": file_size,
                    "lines": total_lines,
                    "is_binary": is_binary,
                    "encoding": None if is_binary else "utf-8",
                }
            )

        except Exception as e:
            return ToolResult.error_result(f"Error reading file: {e}")

    def _resolve_path(self, path: str, working_dir: str) -> Path:
        """Resolve a path relative to working directory."""
        path_obj = Path(path)
        if path_obj.is_absolute():
            return path_obj
        return Path(working_dir) / path_obj

    def _validate_path(self, path: Path, working_dir: str) -> tuple[bool, str | None]:
        """Validate that path is within allowed boundaries."""
        try:
            resolved = path.resolve()
            working_resolved = Path(working_dir).resolve()

            try:
                resolved.relative_to(working_resolved)
                return True, None
            except ValueError:
                return False, "Path traversal detected: path is outside working directory"
        except Exception as e:
            return False, f"Invalid path: {e}"


class FileWriteTool(Tool):
    """Tool for writing files.

    Creates or overwrites files with content validation and backup support.
    """

    name = "file_write"
    description = "Write content to a file"

    DEFAULT_MAX_SIZE = 1024 * 1024  # 1MB

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.max_size = (
            config.get("max_size", self.DEFAULT_MAX_SIZE) if config else self.DEFAULT_MAX_SIZE
        )
        self.create_backup = config.get("create_backup", True) if config else True

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters={
                "path": {
                    "type": "string",
                    "description": "Path to the file to write",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
                "append": {
                    "type": "boolean",
                    "description": "Append to existing file instead of overwriting",
                    "default": False,
                },
            },
            required=["path", "content"],
            category=ToolCategory.FILE_SYSTEM,
            risk_level=ToolRiskLevel.MEDIUM,
            examples=[
                {"path": "output.txt", "content": "Hello World"},
                {"path": "log.txt", "content": "New log entry", "append": True},
            ],
        )

    async def execute(self, context: ToolContext, **params) -> ToolResult:
        file_path = params["path"]
        content = params["content"]
        append = params.get("append", False)

        # Check content size
        content_bytes = content.encode("utf-8")
        if len(content_bytes) > self.max_size:
            return ToolResult.error_result(
                f"Content too large: {len(content_bytes)} bytes (max: {self.max_size})"
            )

        # Resolve path
        resolved_path = self._resolve_path(file_path, context.working_directory)

        # Validate path
        is_valid, error = self._validate_path(resolved_path, context.working_directory)
        if not is_valid:
            return ToolResult.error_result(error or "Path validation failed")

        # Create parent directories
        try:
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return ToolResult.error_result(f"Cannot create directory: {e}")

        # Create backup if file exists and not appending
        backup_path = None
        if resolved_path.exists() and not append and self.create_backup:
            backup_path = resolved_path.with_suffix(resolved_path.suffix + ".backup")
            try:
                backup_path.write_bytes(resolved_path.read_bytes())
            except OSError as e:
                return ToolResult.error_result(f"Cannot create backup: {e}")

        # Write file
        try:
            mode = "a" if append else "w"
            with open(resolved_path, mode, encoding="utf-8") as f:
                f.write(content)

            return ToolResult.success_result(
                {
                    "path": str(resolved_path),
                    "bytes_written": len(content_bytes),
                    "operation": "append" if append else "write",
                    "backup_created": backup_path is not None,
                    "backup_path": str(backup_path) if backup_path else None,
                }
            )

        except Exception as e:
            return ToolResult.error_result(f"Error writing file: {e}")

    def _resolve_path(self, path: str, working_dir: str) -> Path:
        """Resolve a path relative to working directory."""
        path_obj = Path(path)
        if path_obj.is_absolute():
            return path_obj
        return Path(working_dir) / path_obj

    def _validate_path(self, path: Path, working_dir: str) -> tuple[bool, str | None]:
        """Validate that path is within allowed boundaries."""
        try:
            resolved = path.resolve()
            working_resolved = Path(working_dir).resolve()

            if not str(resolved).startswith(str(working_resolved)):
                return False, "Path traversal detected"

            return True, None
        except Exception as e:
            return False, f"Invalid path: {e}"


class FileListTool(Tool):
    """Tool for listing directory contents."""

    name = "file_list"
    description = "List files and directories"

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters={
                "path": {
                    "type": "string",
                    "description": "Directory path to list (default: current directory)",
                    "default": ".",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "List recursively",
                    "default": False,
                },
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to filter files (e.g., '*.py')",
                    "default": "*",
                },
            },
            required=[],
            category=ToolCategory.FILE_SYSTEM,
            risk_level=ToolRiskLevel.LOW,
            examples=[
                {"path": "src"},
                {"path": ".", "recursive": True, "pattern": "*.py"},
            ],
        )

    async def execute(self, context: ToolContext, **params) -> ToolResult:
        dir_path = params.get("path", ".")
        recursive = params.get("recursive", False)
        pattern = params.get("pattern", "*")

        # Resolve path
        resolved_path = self._resolve_path(dir_path, context.working_directory)

        # Validate path
        is_valid, error = self._validate_path(resolved_path, context.working_directory)
        if not is_valid:
            return ToolResult.error_result(error or "Path validation failed")

        # Check exists
        if not resolved_path.exists():
            return ToolResult.error_result(f"Directory not found: {dir_path}")

        if not resolved_path.is_dir():
            return ToolResult.error_result(f"Path is not a directory: {dir_path}")

        # List contents
        try:
            entries = []

            if recursive:
                for item in resolved_path.rglob(pattern):
                    if item.is_file():
                        stat = item.stat()
                        entries.append(
                            {
                                "name": item.name,
                                "path": str(item.relative_to(resolved_path)),
                                "type": "file",
                                "size": stat.st_size,
                            }
                        )
                    elif item.is_dir():
                        entries.append(
                            {
                                "name": item.name,
                                "path": str(item.relative_to(resolved_path)),
                                "type": "directory",
                            }
                        )
            else:
                for item in resolved_path.iterdir():
                    if item.match(pattern) or pattern == "*":
                        if item.is_file():
                            stat = item.stat()
                            entries.append(
                                {
                                    "name": item.name,
                                    "type": "file",
                                    "size": stat.st_size,
                                }
                            )
                        elif item.is_dir():
                            entries.append(
                                {
                                    "name": item.name,
                                    "type": "directory",
                                }
                            )

            # Sort: directories first, then files alphabetically
            entries.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x["name"]))

            return ToolResult.success_result(
                {
                    "path": str(resolved_path),
                    "entries": entries,
                    "total_files": sum(1 for e in entries if e["type"] == "file"),
                    "total_directories": sum(1 for e in entries if e["type"] == "directory"),
                }
            )

        except Exception as e:
            return ToolResult.error_result(f"Error listing directory: {e}")

    def _resolve_path(self, path: str, working_dir: str) -> Path:
        """Resolve a path relative to working directory."""
        path_obj = Path(path)
        if path_obj.is_absolute():
            return path_obj
        return Path(working_dir) / path_obj

    def _validate_path(self, path: Path, working_dir: str) -> tuple[bool, str | None]:
        """Validate that path is within allowed boundaries."""
        try:
            resolved = path.resolve()
            working_resolved = Path(working_dir).resolve()

            if not str(resolved).startswith(str(working_resolved)):
                return False, "Path traversal detected"

            return True, None
        except Exception as e:
            return False, f"Invalid path: {e}"
