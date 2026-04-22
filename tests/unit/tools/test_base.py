"""Tests for tool base classes."""

import pytest

from persona_agent.tools.base import (
    Tool,
    ToolCategory,
    ToolContext,
    ToolResult,
    ToolRiskLevel,
    ToolSchema,
    tool,
)


class TestToolResult:
    """Tests for ToolResult."""

    def test_success_result(self):
        """Test creating a success result."""
        result = ToolResult.success_result({"data": "test"})

        assert result.success is True
        assert result.data == {"data": "test"}
        assert result.error is None

    def test_error_result(self):
        """Test creating an error result."""
        result = ToolResult.error_result("Something went wrong")

        assert result.success is False
        assert result.data is None
        assert result.error == "Something went wrong"

    def test_to_dict_success(self):
        """Test converting success result to dict."""
        result = ToolResult.success_result({"key": "value"})
        data = result.to_dict()

        assert data["success"] is True
        assert data["data"] == {"key": "value"}
        assert data["error"] is None

    def test_to_dict_error(self):
        """Test converting error result to dict."""
        result = ToolResult.error_result("Error message")
        data = result.to_dict()

        assert data["success"] is False
        assert data["data"] is None
        assert data["error"] == "Error message"


class TestToolSchema:
    """Tests for ToolSchema."""

    def test_to_dict(self):
        """Test converting schema to dict."""
        schema = ToolSchema(
            name="test_tool",
            description="A test tool",
            parameters={"input": {"type": "string", "description": "Input value"}},
            required=["input"],
            category=ToolCategory.READ_ONLY,
            risk_level=ToolRiskLevel.LOW,
        )

        data = schema.to_dict()

        assert data["name"] == "test_tool"
        assert data["description"] == "A test tool"
        assert data["parameters"]["input"]["type"] == "string"
        assert data["required"] == ["input"]
        assert data["category"] == "READ_ONLY"
        assert data["risk_level"] == "low"

    def test_to_json_schema(self):
        """Test converting to JSON schema format."""
        schema = ToolSchema(
            name="test_tool",
            description="A test tool",
            parameters={"input": {"type": "string", "description": "Input value"}},
            required=["input"],
            category=ToolCategory.READ_ONLY,
            risk_level=ToolRiskLevel.LOW,
        )

        json_schema = schema.to_json_schema()

        assert json_schema["type"] == "function"
        assert json_schema["function"]["name"] == "test_tool"
        assert json_schema["function"]["description"] == "A test tool"
        assert "input" in json_schema["function"]["parameters"]["properties"]

    def test_to_anthropic_schema(self):
        """Test converting to Anthropic format."""
        schema = ToolSchema(
            name="test_tool",
            description="A test tool",
            parameters={"input": {"type": "string", "description": "Input value"}},
            required=["input"],
            category=ToolCategory.READ_ONLY,
            risk_level=ToolRiskLevel.LOW,
        )

        anthropic_schema = schema.to_anthropic_schema()

        assert anthropic_schema["name"] == "test_tool"
        assert anthropic_schema["description"] == "A test tool"
        assert "input_schema" in anthropic_schema


class TestToolContext:
    """Tests for ToolContext."""

    def test_context_creation(self):
        """Test creating a tool context."""
        context = ToolContext(
            user_id="user123",
            session_id="session456",
        )

        assert context.user_id == "user123"
        assert context.session_id == "session456"
        assert context.memory_store is None
        assert context.permissions == []

    def test_context_with_permissions(self):
        """Test context with permissions."""
        context = ToolContext(
            user_id="user123",
            session_id="session456",
            permissions=["read", "write"],
        )

        assert context.permissions == ["read", "write"]


class TestTool:
    """Tests for Tool base class."""

    def test_tool_requires_name(self):
        """Test that tool subclasses must have a name."""

        class UnnamedTool(Tool):
            description = "A tool without a name"

            async def execute(self, context: ToolContext, **params) -> ToolResult:
                return ToolResult.success_result({})

            def get_schema(self) -> ToolSchema:
                return ToolSchema(
                    name="",
                    description=self.description,
                    parameters={},
                    required=[],
                    category=ToolCategory.READ_ONLY,
                    risk_level=ToolRiskLevel.LOW,
                )

        with pytest.raises(ValueError, match="Tool must have a name"):
            UnnamedTool()

    def test_tool_requires_description(self):
        """Test that tool subclasses must have a description."""

        class NoDescTool(Tool):
            name = "no_desc_tool"

            async def execute(self, context: ToolContext, **params) -> ToolResult:
                return ToolResult.success_result({})

            def get_schema(self) -> ToolSchema:
                return ToolSchema(
                    name=self.name,
                    description="",
                    parameters={},
                    required=[],
                    category=ToolCategory.READ_ONLY,
                    risk_level=ToolRiskLevel.LOW,
                )

        with pytest.raises(ValueError, match="Tool must have a description"):
            NoDescTool()

    def test_tool_version(self):
        """Test tool version default."""

        class TestTool(Tool):
            name = "test_tool"
            description = "A test tool"

            async def execute(self, context: ToolContext, **params) -> ToolResult:
                return ToolResult.success_result({})

            def get_schema(self) -> ToolSchema:
                return ToolSchema(
                    name=self.name,
                    description=self.description,
                    parameters={},
                    required=[],
                    category=ToolCategory.READ_ONLY,
                    risk_level=ToolRiskLevel.LOW,
                )

        tool = TestTool()
        assert tool.version == "1.0.0"

    def test_custom_version(self):
        """Test custom tool version."""

        class VersionedTool(Tool):
            name = "versioned_tool"
            description = "A versioned tool"
            version = "2.5.1"

            async def execute(self, context: ToolContext, **params) -> ToolResult:
                return ToolResult.success_result({})

            def get_schema(self) -> ToolSchema:
                return ToolSchema(
                    name=self.name,
                    description=self.description,
                    parameters={},
                    required=[],
                    category=ToolCategory.READ_ONLY,
                    risk_level=ToolRiskLevel.LOW,
                )

        tool = VersionedTool()
        assert tool.version == "2.5.1"

    def test_get_schema_returns_schema(self):
        """Test that get_schema returns a ToolSchema."""

        class TestTool(Tool):
            name = "test_tool"
            description = "A test tool"

            async def execute(self, context: ToolContext, **params) -> ToolResult:
                return ToolResult.success_result({})

            def get_schema(self) -> ToolSchema:
                return ToolSchema(
                    name=self.name,
                    description=self.description,
                    parameters={"value": {"type": "integer"}},
                    required=["value"],
                    category=ToolCategory.READ_ONLY,
                    risk_level=ToolRiskLevel.LOW,
                )

        tool = TestTool()
        schema = tool.get_schema()

        assert isinstance(schema, ToolSchema)
        assert schema.name == "test_tool"


class TestToolDecorator:
    """Tests for the @tool decorator."""

    def test_decorator_creates_tool_class(self):
        """Test that decorator creates a tool class."""

        @tool(
            name="greet",
            description="Greet someone",
            category=ToolCategory.READ_ONLY,
        )
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        assert hasattr(greet, "_tool_class")

        # Create instance
        tool_instance = greet._tool_class()

        assert tool_instance.name == "greet"
        assert tool_instance.description == "Greet someone"

    def test_decorator_schema_generation(self):
        """Test that decorator generates correct schema."""

        @tool(
            name="calculate",
            description="Calculate sum",
            category=ToolCategory.READ_ONLY,
        )
        def calculate(a: int, b: int) -> int:
            """Add two numbers.

            Args:
                a: First number
                b: Second number
            """
            return a + b

        tool_instance = calculate._tool_class()
        schema = tool_instance.get_schema()

        assert schema.name == "calculate"
        assert "a" in schema.parameters
        assert "b" in schema.parameters
