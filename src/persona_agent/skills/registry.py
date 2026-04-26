"""Skill registry with lazy loading capabilities."""

import importlib
import inspect
import logging
from pathlib import Path
from typing import Any, TypeVar

from persona_agent.skills.base import BaseSkill, SkillContext, SkillResult

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseSkill)


class SkillRegistry:
    """Registry for managing skills with lazy loading.

    The registry maintains a catalog of available skills and loads them
    on-demand to minimize memory usage and startup time.

    Example:
        registry = SkillRegistry()

        # Register skills
        registry.register_class(WeatherSkill)
        registry.register_module("persona_agent.skills.built_in")

        # Discover skills from directory
        registry.discover_skills(Path("./skills"))

        # Execute skills
        result = await registry.execute_matching(context)
    """

    def __init__(self):
        """Initialize an empty skill registry."""
        # Maps skill name to (skill_class, is_loaded, instance)
        self._skills: dict[str, tuple[type[BaseSkill], bool, BaseSkill | None]] = {}
        self._skill_order: list[str] = []  # Ordered by priority

    def register_class(self, skill_class: type[BaseSkill]) -> None:
        """Register a skill class.

        Args:
            skill_class: The skill class to register

        Raises:
            ValueError: If skill name is empty or already registered
        """
        if not skill_class.name:
            raise ValueError(f"Skill class {skill_class.__name__} has no name")

        if skill_class.name in self._skills:
            logger.warning(f"Skill '{skill_class.name}' already registered, overwriting")

        self._skills[skill_class.name] = (skill_class, False, None)
        self._update_skill_order()

        logger.debug(f"Registered skill: {skill_class.name}")

    def register_module(self, module_path: str) -> int:
        """Register all skills from a module.

        Automatically discovers and registers all BaseSkill subclasses
        in the given module.

        Args:
            module_path: Python import path (e.g., "persona_agent.skills.built_in")

        Returns:
            Number of skills registered
        """
        try:
            module = importlib.import_module(module_path)
        except ImportError as e:
            logger.error(f"Failed to import module {module_path}: {e}")
            return 0

        count = 0
        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, BaseSkill)
                and obj is not BaseSkill
                and not inspect.isabstract(obj)
                and obj.name  # Has a name defined
            ):
                self.register_class(obj)
                count += 1

        logger.info(f"Registered {count} skills from {module_path}")
        return count

    def discover_skills(self, skills_dir: Path, package_prefix: str = "skills") -> int:
        """Discover and register skills from a directory.

        Scans the directory for Python files and attempts to import them
        as skill modules.

        Args:
            skills_dir: Directory containing skill modules
            package_prefix: Python package prefix for imports

        Returns:
            Number of skills discovered and registered
        """
        if not skills_dir.exists():
            logger.warning(f"Skills directory not found: {skills_dir}")
            return 0

        count = 0
        for file_path in skills_dir.glob("*.py"):
            if file_path.name.startswith("_"):
                continue

            module_name = file_path.stem
            full_module_path = f"{package_prefix}.{module_name}"

            # Temporarily add to path if needed
            if str(skills_dir.parent) not in importlib.sys.path:
                importlib.sys.path.insert(0, str(skills_dir.parent))

            try:
                registered = self.register_module(full_module_path)
                count += registered
            except (ValueError, RuntimeError) as e:
                logger.error(f"Failed to load skill module {module_name}: {e}")

        logger.info(f"Discovered {count} skills from {skills_dir}")
        return count

    async def load_skill(self, name: str, config: dict[str, Any] | None = None) -> BaseSkill:
        """Load a skill by name (lazy loading).

        Args:
            name: Skill name
            config: Optional configuration for the skill

        Returns:
            Loaded skill instance

        Raises:
            KeyError: If skill not found
        """
        if name not in self._skills:
            raise KeyError(f"Skill '{name}' not found in registry")

        skill_class, is_loaded, instance = self._skills[name]

        if is_loaded and instance is not None:
            return instance

        # Create and initialize
        instance = skill_class(config)
        await instance.initialize()

        self._skills[name] = (skill_class, True, instance)
        logger.debug(f"Lazy-loaded skill: {name}")

        return instance

    async def unload_skill(self, name: str) -> None:
        """Unload a skill and cleanup resources.

        Args:
            name: Skill name
        """
        if name not in self._skills:
            return

        skill_class, is_loaded, instance = self._skills[name]

        if is_loaded and instance is not None:
            await instance.cleanup()
            self._skills[name] = (skill_class, False, None)
            logger.debug(f"Unloaded skill: {name}")

    async def execute_matching(
        self, context: SkillContext, load_all: bool = False
    ) -> SkillResult | None:
        """Execute the first skill that can handle the context.

        Args:
            context: Execution context
            load_all: If True, load all skills before checking (slower)

        Returns:
            Skill result if a skill handled the input, None otherwise
        """
        for name in self._skill_order:
            skill_class, is_loaded, instance = self._skills[name]

            if not skill_class.enabled:
                continue

            try:
                if load_all or is_loaded:
                    # Use loaded instance or load it
                    if instance is None:
                        instance = await self.load_skill(name)

                    if await instance.can_handle(context):
                        logger.info(f"Executing skill: {name}")
                        return await instance.execute(context)
                else:
                    # Quick check using class method if available
                    # This allows checking without loading
                    if hasattr(skill_class, "can_handle"):
                        # Create temporary instance for checking
                        temp_instance = skill_class()
                        if await temp_instance.can_handle(context):
                            # Now properly load and execute
                            instance = await self.load_skill(name)
                            logger.info(f"Executing skill: {name}")
                            return await instance.execute(context)

            except (ValueError, RuntimeError) as e:
                logger.error(f"Error executing skill '{name}': {e}")
                continue

        return None

    def list_skills(self, include_unloaded: bool = True) -> list[dict[str, Any]]:
        """List all registered skills.

        Args:
            include_unloaded: Include skills that haven't been loaded yet

        Returns:
            List of skill information dictionaries
        """
        skills = []
        for name in self._skill_order:
            skill_class, is_loaded, instance = self._skills[name]

            if not include_unloaded and not is_loaded:
                continue

            skills.append(
                {
                    "name": name,
                    "description": skill_class.description,
                    "version": skill_class.version,
                    "priority": skill_class.priority,
                    "enabled": skill_class.enabled,
                    "loaded": is_loaded,
                }
            )

        return skills

    def get_skill(self, name: str) -> type[BaseSkill] | None:
        """Get a skill class by name.

        Args:
            name: Skill name

        Returns:
            Skill class or None if not found
        """
        if name in self._skills:
            return self._skills[name][0]
        return None

    def _update_skill_order(self) -> None:
        """Update skill execution order based on priority."""
        # Sort by priority (descending), then by name for stability
        self._skill_order = sorted(
            self._skills.keys(),
            key=lambda name: (-self._skills[name][0].priority, name),
        )

    async def unload_all(self) -> None:
        """Unload all skills and cleanup."""
        for name in list(self._skills.keys()):
            await self.unload_skill(name)


# Global registry instance
_global_registry: SkillRegistry | None = None


def get_registry() -> SkillRegistry:
    """Get the global skill registry instance.

    Returns:
        The global SkillRegistry (creates one if needed)
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = SkillRegistry()
    return _global_registry


def reset_registry() -> None:
    """Reset the global registry (useful for testing)."""
    global _global_registry
    _global_registry = None
