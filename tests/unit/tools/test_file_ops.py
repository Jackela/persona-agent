"""Tests for file operation tools."""

import tempfile
from pathlib import Path

import pytest

from persona_agent.tools.base import ToolContext
from persona_agent.tools.file_ops import FileListTool, FileReadTool, FileWriteTool


class TestFileReadTool:
    """Tests for FileReadTool."""

    @pytest.fixture
    def tool(self):
        return FileReadTool()

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp

    @pytest.fixture
    def context(self, temp_dir):
        return ToolContext(
            user_id="test_user",
            session_id="test_session",
            working_directory=temp_dir,
        )

    async def test_read_file_success(self, tool, context, temp_dir):
        """Test successfully reading a file."""
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("Hello, World!")

        result = await tool.execute(context, path=str(test_file))

        assert result.success is True
        assert result.data["content"] == "Hello, World!"
        assert result.data["path"] == str(test_file)

    async def test_read_file_not_found(self, tool, context, temp_dir):
        """Test reading a non-existent file."""
        missing_file = Path(temp_dir) / "missing.txt"

        result = await tool.execute(context, path=str(missing_file))

        assert result.success is False
        assert "not found" in result.error.lower()

    async def test_read_file_path_traversal(self, tool, context):
        """Test path traversal protection."""
        result = await tool.execute(context, path="../../etc/passwd")

        assert result.success is False
        assert "traversal" in result.error.lower()

    async def test_read_file_with_offset(self, tool, context, temp_dir):
        """Test reading file with offset."""
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("Line 1\nLine 2\nLine 3\n")

        result = await tool.execute(context, path=str(test_file), offset=1)

        assert result.success is True
        assert "Line 2" in result.data["content"]
        assert "Line 1" not in result.data["content"]

    async def test_read_file_with_limit(self, tool, context, temp_dir):
        """Test reading file with line limit."""
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("Line 1\nLine 2\nLine 3\nLine 4\n")

        result = await tool.execute(context, path=str(test_file), limit=2)

        assert result.success is True
        assert result.data["lines"] == 2

    async def test_read_binary_file(self, tool, context, temp_dir):
        """Test reading binary file - extension not allowed."""
        test_file = Path(temp_dir) / "binary.dat"
        test_file.write_bytes(b"\x00\x01\x02\x03")

        result = await tool.execute(context, path=str(test_file))

        assert result.success is False
        assert "not allowed" in result.error.lower()


class TestFileWriteTool:
    """Tests for FileWriteTool."""

    @pytest.fixture
    def tool(self):
        return FileWriteTool()

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp

    @pytest.fixture
    def context(self, temp_dir):
        return ToolContext(
            user_id="test_user",
            session_id="test_session",
            working_directory=temp_dir,
        )

    async def test_write_file_success(self, tool, context, temp_dir):
        """Test successfully writing a file."""
        test_file = Path(temp_dir) / "output.txt"

        result = await tool.execute(context, path=str(test_file), content="Test content")

        assert result.success is True
        assert test_file.read_text() == "Test content"

    async def test_write_file_creates_directory(self, tool, context, temp_dir):
        """Test that writing creates parent directories."""
        test_file = Path(temp_dir) / "subdir" / "nested" / "file.txt"

        result = await tool.execute(context, path=str(test_file), content="Nested content")

        assert result.success is True
        assert test_file.exists()
        assert test_file.read_text() == "Nested content"

    async def test_write_file_with_backup(self, tool, context, temp_dir):
        """Test backup creation when overwriting."""
        test_file = Path(temp_dir) / "existing.txt"
        test_file.write_text("Original content")

        result = await tool.execute(
            context,
            path=str(test_file),
            content="New content",
            backup=True,
        )

        assert result.success is True
        assert test_file.read_text() == "New content"
        assert result.data["backup_created"] is True
        assert result.data["backup_path"] is not None

    async def test_write_file_no_backup(self, tool, context, temp_dir):
        """Test overwriting without backup."""
        test_file = Path(temp_dir) / "existing.txt"
        test_file.write_text("Original content")

        # Create tool with backup disabled via config
        tool_no_backup = FileWriteTool(config={"create_backup": False})

        result = await tool_no_backup.execute(
            context,
            path=str(test_file),
            content="New content",
        )

        assert result.success is True
        assert result.data["backup_created"] is False

    async def test_write_file_path_traversal(self, tool, context):
        """Test path traversal protection."""
        result = await tool.execute(
            context,
            path="../../etc/passwd",
            content="Malicious content",
        )

        assert result.success is False
        assert "traversal" in result.error.lower()


class TestFileListTool:
    """Tests for FileListTool."""

    @pytest.fixture
    def tool(self):
        return FileListTool()

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Create some test files
            Path(tmp, "file1.txt").touch()
            Path(tmp, "file2.py").touch()
            Path(tmp, "subdir").mkdir()
            yield tmp

    @pytest.fixture
    def context(self, temp_dir):
        return ToolContext(
            user_id="test_user",
            session_id="test_session",
            working_directory=temp_dir,
        )

    async def test_list_directory(self, tool, context, temp_dir):
        """Test listing directory contents."""
        result = await tool.execute(context, path=".")

        assert result.success is True
        assert result.data["total_files"] == 2
        assert result.data["total_directories"] == 1
        assert len(result.data["entries"]) == 3  # 2 files + 1 subdir

    async def test_list_directory_not_found(self, tool, context):
        """Test listing non-existent directory."""
        result = await tool.execute(context, path="nonexistent_directory_12345")

        assert result.success is False
        assert "not found" in result.error.lower()

    async def test_list_directory_path_traversal(self, tool, context):
        """Test path traversal protection."""
        result = await tool.execute(context, path="../../etc")

        assert result.success is False
        assert "traversal" in result.error.lower()

    async def test_list_directory_recursive(self, tool, context, temp_dir):
        """Test recursive directory listing."""
        # Create nested file
        Path(temp_dir, "subdir", "nested.txt").touch()

        result = await tool.execute(context, path=temp_dir, recursive=True)

        assert result.success is True
        # Should include the nested file
        all_paths = [e["path"] for e in result.data["entries"]]
        assert any("nested.txt" in p for p in all_paths)


class TestFileOpsIntegration:
    """Integration tests for file operations."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp

    @pytest.fixture
    def context(self, temp_dir):
        return ToolContext(
            user_id="test_user",
            session_id="test_session",
            working_directory=temp_dir,
        )

    async def test_read_write_roundtrip(self, temp_dir, context):
        """Test writing and reading back a file."""
        read_tool = FileReadTool()
        write_tool = FileWriteTool()
        test_file = Path(temp_dir) / "roundtrip.txt"
        test_content = "Roundtrip test content"

        # Write
        write_result = await write_tool.execute(context, path=str(test_file), content=test_content)
        assert write_result.success is True

        # Read
        read_result = await read_tool.execute(context, path=str(test_file))
        assert read_result.success is True
        assert read_result.data["content"] == test_content
