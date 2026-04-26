"""Tool discovery and registry system.

This module provides dynamic tool registration, discovery, and management.
Tools can be registered at runtime, discovered via metadata, and loaded on demand.
"""

from __future__ import annotations

import importlib
import inspect
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from persona_agent.tools.base import Tool, ToolCategory, ToolRiskLevel, ToolSchema

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Tool)


@dataclass
class ToolMetadata:
    """Metadata about a registered tool.

    Attributes:
        name: Tool name
        description: Tool description
        category: Tool category
        risk_level: Risk level
        version: Tool version
        module: Module where tool is defined
        class_name: Class name of the tool
        instance: Tool instance (if loaded)
        is_loaded: Whether the tool is loaded
    """

    name: str
    description: str
    category: ToolCategory
    risk_level: ToolRiskLevel
    version: str
    module: str
    class_name: str
    instance: Tool | None = None
    is_loaded: bool = False
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.name,
            "risk_level": self.risk_level.value,
            "version": self.version,
            "module": self.module,
            "class_name": self.class_name,
            "is_loaded": self.is_loaded,
        }


class ToolRegistry:
    """Registry for managing and discovering tools.

    The registry provides:
    - Tool registration and lookup
    - Lazy loading of tools
    - Tool discovery from modules
    - Schema generation

    Example:
        registry = ToolRegistry()
        registry.register(FileReadTool)

        # Get tool instance
        tool = registry.get_tool("file_read")
        result = await tool.run(context, path="example.txt")
    """

    def __init__(self):
        """Initialize the tool registry."""
        self._tools: dict[str, ToolMetadata] = {}
        self._tool_classes: dict[str, type[Tool]] = {}

    def register(
        self,
        tool_class: type[T],
        config: dict[str, Any] | None = None,
    ) -> ToolMetadata:
        """Register a tool class.

        Args:
            tool_class: Tool class to register
            config: Optional configuration for the tool

        Returns:
            ToolMetadata for the registered tool

        Raises:
            ValueError: If tool name is empty or already registered
        """
        if not tool_class.name:
            raise ValueError("Tool class must have a name")

        if tool_class.name in self._tools:
            logger.warning(f"Tool '{tool_class.name}' is already registered, skipping")
            return self._tools[tool_class.name]

        # Create temporary instance to get schema
        temp_instance = tool_class(config)
        schema = temp_instance.get_schema()

        metadata = ToolMetadata(
            name=tool_class.name,
            description=tool_class.description,
            category=schema.category,
            risk_level=schema.risk_level,
            version=tool_class.version,
            module=tool_class.__module__,
            class_name=tool_class.__name__,
            config=config or {},
        )

        self._tools[tool_class.name] = metadata
        self._tool_classes[tool_class.name] = tool_class

        logger.debug(f"Registered tool: {tool_class.name}")
        return metadata

    def unregister(self, name: str) -> bool:
        """Unregister a tool.

        Args:
            name: Tool name

        Returns:
            True if tool was unregistered, False if not found
        """
        if name in self._tools:
            del self._tools[name]
            del self._tool_classes[name]
            logger.debug(f"Unregistered tool: {name}")
            return True
        return False

    def get_tool(self, name: str) -> Tool | None:
        """Get a loaded tool instance.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        metadata = self._tools.get(name)
        if not metadata:
            return None

        # Load if not already loaded
        if metadata.instance is None:
            self._load_tool(name)

        return metadata.instance

    def get_metadata(self, name: str) -> ToolMetadata | None:
        """Get tool metadata.

        Args:
            name: Tool name

        Returns:
            ToolMetadata or None if not found
        """
        return self._tools.get(name)

    def get_schema(self, name: str) -> ToolSchema | None:
        """Get tool schema.

        Args:
            name: Tool name

        Returns:
            ToolSchema or None if not found
        """
        tool = self.get_tool(name)
        if tool:
            return tool.get_schema()
        return None

    def list_tools(
        self,
        category: ToolCategory | None = None,
        max_risk: ToolRiskLevel | None = None,
    ) -> list[ToolMetadata]:
        """List registered tools with optional filtering.

        Args:
            category: Filter by category
            max_risk: Maximum risk level to include

        Returns:
            List of tool metadata
        """
        tools = list(self._tools.values())

        if category:
            tools = [t for t in tools if t.category == category]

        if max_risk:
            risk_order = {
                ToolRiskLevel.LOW: 0,
                ToolRiskLevel.MEDIUM: 1,
                ToolRiskLevel.HIGH: 2,
                ToolRiskLevel.CRITICAL: 3,
            }
            max_level = risk_order.get(max_risk, 3)
            tools = [t for t in tools if risk_order.get(t.risk_level, 3) <= max_level]

        return tools

    def list_schemas(self) -> list[ToolSchema]:
        """List schemas for all registered tools.

        Returns:
            List of tool schemas
        """
        schemas = []
        for name in self._tools:
            schema = self.get_schema(name)
            if schema:
                schemas.append(schema)
        return schemas

    def _load_tool(self, name: str) -> Tool | None:
        """Load a tool instance.

        Args:
            name: Tool name

        Returns:
            Loaded tool instance or None
        """
        metadata = self._tools.get(name)
        tool_class = self._tool_classes.get(name)

        if not metadata or not tool_class:
            return None

        try:
            instance = tool_class(metadata.config)
            metadata.instance = instance
            metadata.is_loaded = True
            logger.debug(f"Loaded tool: {name}")
            return instance
        except (ValueError, RuntimeError) as e:
            logger.error(f"Failed to load tool '{name}': {e}")
            return None

    def discover_from_module(self, module_path: str) -> list[ToolMetadata]:
        """Discover tools from a module.

        Args:
            module_path: Python module path (e.g., "persona_agent.tools.file_ops")

        Returns:
            List of discovered tool metadata
        """
        discovered: list[ToolMetadata] = []

        try:
            module = importlib.import_module(module_path)
        except ImportError as e:
            logger.error(f"Failed to import module '{module_path}': {e}")
            return discovered

        # Find Tool subclasses
        for _name, obj in inspect.getmembers(module):
            if (
                inspect.isclass(obj)
                and issubclass(obj, Tool)
                and obj is not Tool
                and not getattr(obj, "_abstract", False)
            ):
                try:
                    metadata = self.register(obj)
                    discovered.append(metadata)
                except ValueError:
                    pass  # Already registered or invalid

        return discovered

    def discover_from_directory(self, directory: Path | str) -> list[ToolMetadata]:
        """Discover tools from Python files in a directory.

        Args:
            directory: Directory containing tool modules

        Returns:
            List of discovered tool metadata
        """
        directory = Path(directory)
        discovered: list[ToolMetadata] = []

        if not directory.exists():
            logger.warning(f"Directory not found: {directory}")
            return discovered

        for py_file in directory.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            # Convert file path to module path
            # This is a simplified version - in production use proper package discovery
            module_name = py_file.stem
            try:
                # Try to import as persona_agent.tools.{module_name}
                full_path = f"persona_agent.tools.{module_name}"
                discovered.extend(self.discover_from_module(full_path))
            except ImportError:
                logger.debug(f"Could not import {module_name}")

        return discovered

    def get_all_schemas_for_llm(self, provider: str = "ollama") -> list[dict[str, Any]]:
        """Get all tool schemas formatted for LLM function calling.

        Args:
            provider: LLM provider (openai, anthropic)

        Returns:
            List of tool schemas in provider format
        """
        schemas = []
        for name in self._tools:
            tool = self.get_tool(name)
            if tool:
                schema = tool.get_schema()
                if provider == "openai":
                    schemas.append(schema.to_json_schema())
                elif provider == "anthropic":
                    schemas.append(schema.to_anthropic_schema())
                else:
                    schemas.append(schema.to_dict())
        return schemas


class ToolDiscovery:
    """Service for discovering tools from various sources.

    Provides high-level discovery capabilities:
    - Auto-discovery from built-in modules
    - Discovery from installed packages
    - Dynamic tool loading
    """

    BUILTIN_TOOL_MODULES = [
        "persona_agent.tools.file_ops",
        "persona_agent.tools.code_exec",
        "persona_agent.tools.web_search",
        "persona_agent.tools.memory_tool",
    ]

    def __init__(self, registry: ToolRegistry | None = None):
        """Initialize discovery service.

        Args:
            registry: Tool registry to use (creates new if None)
        """
        self.registry = registry or ToolRegistry()

    def discover_builtin_tools(self) -> list[ToolMetadata]:
        """Discover all built-in tools.

        Returns:
            List of discovered tool metadata
        """
        discovered = []
        for module_path in self.BUILTIN_TOOL_MODULES:
            try:
                found = self.registry.discover_from_module(module_path)
                discovered.extend(found)
            except (ValueError, RuntimeError) as e:
                logger.warning(f"Failed to discover from {module_path}: {e}")
        return discovered

    def discover_all(self) -> list[ToolMetadata]:
        """Run full discovery process.

        Returns:
            List of all discovered tools
        """
        discovered = []

        # Discover built-in tools
        discovered.extend(self.discover_builtin_tools())

        # Discover from tools directory
        tools_dir = Path(__file__).parent
        discovered.extend(self.registry.discover_from_directory(tools_dir))

        logger.info(f"Discovered {len(discovered)} tools")
        return discovered


def get_default_registry() -> ToolRegistry:
    """Get or create the default tool registry with all tools registered."""
    registry = ToolRegistry()
    discovery = ToolDiscovery(registry)
    discovery.discover_all()
    return registry
