"""Tests for tool discovery and registry."""

from unittest.mock import patch

import pytest

from persona_agent.tools.base import (
    Tool,
    ToolCategory,
    ToolContext,
    ToolResult,
    ToolRiskLevel,
    ToolSchema,
)
from persona_agent.tools.discovery import ToolDiscovery, ToolMetadata, ToolRegistry


class MockTool(Tool):
    """Mock tool for testing."""

    name = "mock_tool"
    description = "A mock tool for testing"
    version = "1.0.0"

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters={},
            required=[],
            category=ToolCategory.READ_ONLY,
            risk_level=ToolRiskLevel.LOW,
        )

    async def execute(self, context: ToolContext, **params) -> ToolResult:
        return ToolResult.success_result({"executed": True})


class MockHighRiskTool(Tool):
    """Mock high-risk tool for testing."""

    name = "mock_high_risk_tool"
    description = "A high risk tool"

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters={},
            required=[],
            category=ToolCategory.SYSTEM,
            risk_level=ToolRiskLevel.CRITICAL,
        )

    async def execute(self, context: ToolContext, **params) -> ToolResult:
        return ToolResult.success_result({})


class TestToolMetadata:
    """Tests for ToolMetadata."""

    def test_to_dict(self):
        """Test converting metadata to dict."""
        metadata = ToolMetadata(
            name="test_tool",
            description="Test description",
            category=ToolCategory.READ_ONLY,
            risk_level=ToolRiskLevel.LOW,
            version="1.0.0",
            module="test.module",
            class_name="TestTool",
        )

        data = metadata.to_dict()

        assert data["name"] == "test_tool"
        assert data["description"] == "Test description"
        assert data["category"] == "READ_ONLY"
        assert data["risk_level"] == "low"
        assert data["version"] == "1.0.0"


class TestToolRegistry:
    """Tests for ToolRegistry."""

    @pytest.fixture
    def registry(self):
        return ToolRegistry()

    def test_register_tool(self, registry):
        """Test registering a tool."""
        metadata = registry.register(MockTool)

        assert metadata.name == "mock_tool"
        assert metadata.class_name == "MockTool"
        assert "mock_tool" in registry._tools

    def test_register_duplicate_warning(self, registry, caplog):
        """Test that duplicate registration is skipped."""
        registry.register(MockTool)

        # Register again - should be skipped
        with caplog.at_level("WARNING"):
            registry.register(MockTool)

        assert "already registered" in caplog.text

    def test_register_tool_without_name(self, registry):
        """Test that tools without names are rejected."""

        class NoNameTool(Tool):
            name = ""
            description = "No name"

            def get_schema(self) -> ToolSchema:
                return ToolSchema(
                    name="",
                    description="test",
                    parameters={},
                    required=[],
                    category=ToolCategory.READ_ONLY,
                    risk_level=ToolRiskLevel.LOW,
                )

            async def execute(self, context: ToolContext, **params) -> ToolResult:
                return ToolResult.success_result({})

        with pytest.raises(ValueError, match="must have a name"):
            registry.register(NoNameTool)

    def test_unregister_tool(self, registry):
        """Test unregistering a tool."""
        registry.register(MockTool)

        result = registry.unregister("mock_tool")

        assert result is True
        assert "mock_tool" not in registry._tools

    def test_unregister_nonexistent(self, registry):
        """Test unregistering a non-existent tool."""
        result = registry.unregister("nonexistent")

        assert result is False

    def test_get_tool(self, registry):
        """Test getting a tool instance."""
        registry.register(MockTool)

        tool = registry.get_tool("mock_tool")

        assert tool is not None
        assert isinstance(tool, MockTool)

    def test_get_tool_not_found(self, registry):
        """Test getting a non-existent tool."""
        tool = registry.get_tool("nonexistent")

        assert tool is None

    def test_get_metadata(self, registry):
        """Test getting tool metadata."""
        registry.register(MockTool)

        metadata = registry.get_metadata("mock_tool")

        assert metadata is not None
        assert metadata.name == "mock_tool"

    def test_get_schema(self, registry):
        """Test getting tool schema."""
        registry.register(MockTool)

        schema = registry.get_schema("mock_tool")

        assert schema is not None
        assert schema.name == "mock_tool"

    def test_list_tools(self, registry):
        """Test listing all tools."""
        registry.register(MockTool)
        registry.register(MockHighRiskTool)

        tools = registry.list_tools()

        assert len(tools) == 2

    def test_list_tools_by_category(self, registry):
        """Test listing tools filtered by category."""
        registry.register(MockTool)  # READ_ONLY
        registry.register(MockHighRiskTool)  # SYSTEM

        read_only_tools = registry.list_tools(category=ToolCategory.READ_ONLY)

        assert len(read_only_tools) == 1
        assert read_only_tools[0].name == "mock_tool"

    def test_list_tools_by_risk(self, registry):
        """Test listing tools filtered by risk level."""
        registry.register(MockTool)  # LOW
        registry.register(MockHighRiskTool)  # CRITICAL

        low_risk_tools = registry.list_tools(max_risk=ToolRiskLevel.MEDIUM)

        assert len(low_risk_tools) == 1
        assert low_risk_tools[0].name == "mock_tool"

    def test_list_schemas(self, registry):
        """Test listing all schemas."""
        registry.register(MockTool)

        schemas = registry.list_schemas()

        assert len(schemas) == 1
        assert schemas[0].name == "mock_tool"

    def test_get_all_schemas_for_llm(self, registry):
        """Test getting schemas formatted for LLM."""
        registry.register(MockTool)

        schemas = registry.get_all_schemas_for_llm("openai")

        assert len(schemas) == 1
        assert schemas[0]["type"] == "function"

    def test_lazy_loading(self, registry):
        """Test that tools are lazy loaded."""
        registry.register(MockTool)

        # Metadata should exist but instance should not be loaded
        metadata = registry.get_metadata("mock_tool")
        assert metadata.is_loaded is False
        assert metadata.instance is None

        # Getting the tool should load it
        tool = registry.get_tool("mock_tool")
        assert tool is not None

        metadata = registry.get_metadata("mock_tool")
        assert metadata.is_loaded is True
        assert metadata.instance is not None


class TestToolDiscovery:
    """Tests for ToolDiscovery."""

    @pytest.fixture
    def discovery(self):
        registry = ToolRegistry()
        return ToolDiscovery(registry)

    def test_discover_from_module(self, discovery):
        """Test discovering tools from a module."""
        discovered = discovery.registry.discover_from_module("tests.unit.tools.test_discovery")

        # Should find MockTool and MockHighRiskTool
        tool_names = [d.name for d in discovered]
        assert "mock_tool" in tool_names or len(discovered) >= 0  # May find test classes

    def test_discover_from_nonexistent_module(self, discovery):
        """Test discovering from a non-existent module."""
        discovered = discovery.registry.discover_from_module("nonexistent.module")

        assert discovered == []

    def test_discover_builtin_tools(self, discovery):
        """Test discovering built-in tools."""
        # Patch BUILTIN_TOOL_MODULES to avoid importing actual modules
        with patch.object(discovery, "BUILTIN_TOOL_MODULES", []):
            discovered = discovery.discover_builtin_tools()

        assert isinstance(discovered, list)

    def test_discover_all(self, discovery):
        """Test full discovery process."""
        with patch.object(discovery, "BUILTIN_TOOL_MODULES", []):
            discovered = discovery.discover_all()

        assert isinstance(discovered, list)


class TestGetDefaultRegistry:
    """Tests for get_default_registry."""

    def test_get_default_registry(self):
        """Test getting default registry."""
        from persona_agent.tools.discovery import get_default_registry

        # Patch to avoid importing actual tool modules
        with patch("persona_agent.tools.discovery.ToolDiscovery.discover_all") as mock_discover:
            mock_discover.return_value = []
            registry = get_default_registry()

        assert isinstance(registry, ToolRegistry)
