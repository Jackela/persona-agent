"""Base skill class and interfaces for the skill system."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillContext:
    """Context passed to skills during execution.

    Contains all information a skill might need to perform its function.
    """

    user_input: str
    conversation_history: list[dict] = field(default_factory=list)
    current_mood: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    memory_store: Any | None = None
    persona_manager: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillResult:
    """Result returned by a skill execution.

    Skills can return text responses, tool calls, or trigger events.
    """

    success: bool
    response: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)
    confidence: float = 1.0


class BaseSkill(ABC):
    """Abstract base class for all skills.

    Skills are modular capabilities that can be dynamically loaded and executed.
    They follow a lifecycle: initialize -> can_handle -> execute -> cleanup.

    Example:
        class WeatherSkill(BaseSkill):
            name = "weather"
            description = "Get weather information"

            async def can_handle(self, context: SkillContext) -> bool:
                return "天气" in context.user_input

            async def execute(self, context: SkillContext) -> SkillResult:
                # Fetch weather and return result
                return SkillResult(success=True, response="今天晴天")
    """

    # Class attributes that must be defined by subclasses
    name: str = ""
    description: str = ""
    version: str = "1.0.0"

    # Configuration
    priority: int = 0  # Higher priority skills are checked first
    enabled: bool = True
    requires_auth: bool = False

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the skill with optional configuration.

        Args:
            config: Skill-specific configuration dictionary
        """
        self.config = config or {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the skill.

        Called once when the skill is first loaded. Override to set up
        resources, load models, connect to APIs, etc.
        """
        self._initialized = True

    async def cleanup(self) -> None:
        """Cleanup resources when skill is unloaded.

        Override to release resources, close connections, etc.
        """
        self._initialized = False

    @abstractmethod
    async def can_handle(self, context: SkillContext) -> bool:
        """Check if this skill can handle the given context.

        This is the routing logic - return True if your skill should
        handle this input.

        Args:
            context: The current execution context

        Returns:
            True if this skill can handle the input
        """
        pass

    @abstractmethod
    async def execute(self, context: SkillContext) -> SkillResult:
        """Execute the skill.

        Perform the skill's main functionality and return a result.

        Args:
            context: The current execution context

        Returns:
            SkillResult containing the outcome
        """
        pass

    def get_help(self) -> str:
        """Return help text for this skill.

        Returns:
            Human-readable description of what the skill does
        """
        return f"{self.name}: {self.description}"


class SkillDecorator:
    """Decorator for creating simple skills from functions.

    Example:
        @skill(name="echo", description="Echo back the input")
        async def echo_skill(context: SkillContext) -> SkillResult:
            return SkillResult(success=True, response=context.user_input)
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        priority: int = 0,
        enabled: bool = True,
    ):
        self.name = name
        self.description = description
        self.priority = priority
        self.enabled = enabled

    def __call__(self, func: Callable[[SkillContext], SkillResult]) -> type[BaseSkill]:
        """Create a skill class from a function.

        Args:
            func: Async function that takes SkillContext and returns SkillResult

        Returns:
            A new skill class
        """

        class FunctionSkill(BaseSkill):
            name = self.name
            description = self.description
            priority = self.priority
            enabled = self.enabled

            async def can_handle(self, context: SkillContext) -> bool:
                # By default, function skills always trigger
                # Override by providing a can_handle function
                return True

            async def execute(self, context: SkillContext) -> SkillResult:
                return await func(context)

        # Copy function name for debugging
        FunctionSkill.__name__ = f"{self.name.title()}Skill"
        return FunctionSkill


# Convenience alias
skill = SkillDecorator
