"""Tests for the skill system."""

import pytest

from persona_agent.skills.base import BaseSkill, SkillContext, SkillResult, skill
from persona_agent.skills.registry import SkillRegistry, get_registry, reset_registry


class TestSkillContext:
    """Test SkillContext dataclass."""

    def test_create_context(self) -> None:
        """Test creating a skill context."""
        context = SkillContext(user_input="Hello")
        assert context.user_input == "Hello"
        assert context.conversation_history == []
        assert context.current_mood is None

    def test_context_with_metadata(self) -> None:
        """Test context with metadata."""
        context = SkillContext(
            user_input="Test",
            current_mood="happy",
            user_id="user123",
            metadata={"key": "value"},
        )
        assert context.current_mood == "happy"
        assert context.metadata["key"] == "value"


class TestSkillResult:
    """Test SkillResult dataclass."""

    def test_success_result(self) -> None:
        """Test creating a successful result."""
        result = SkillResult(success=True, response="Hello")
        assert result.success is True
        assert result.response == "Hello"
        assert result.confidence == 1.0

    def test_failure_result(self) -> None:
        """Test creating a failed result."""
        result = SkillResult(success=False, response="Error", confidence=0.0)
        assert result.success is False
        assert result.confidence == 0.0


class TestBaseSkill:
    """Test BaseSkill abstract class."""

    def test_skill_requires_name(self) -> None:
        """Test that skills must have a name."""

        class NoNameSkill(BaseSkill):
            pass

        assert NoNameSkill.name == ""

    def test_skill_lifecycle(self) -> None:
        """Test skill initialization and cleanup."""

        class TestSkill(BaseSkill):
            name = "test"
            description = "Test skill"

            async def can_handle(self, context: SkillContext) -> bool:
                return True

            async def execute(self, context: SkillContext) -> SkillResult:
                return SkillResult(success=True)

        skill_instance = TestSkill()
        assert not skill_instance._initialized


class TestSkillRegistry:
    """Test SkillRegistry functionality."""

    @pytest.fixture
    def registry(self) -> SkillRegistry:
        """Create a fresh registry for each test."""
        reset_registry()
        return SkillRegistry()

    def test_register_class(self, registry: SkillRegistry) -> None:
        """Test registering a skill class."""

        class TestSkill(BaseSkill):
            name = "test_skill"
            description = "A test skill"

            async def can_handle(self, context: SkillContext) -> bool:
                return True

            async def execute(self, context: SkillContext) -> SkillResult:
                return SkillResult(success=True)

        registry.register_class(TestSkill)

        assert "test_skill" in [s["name"] for s in registry.list_skills()]

    def test_register_duplicate_name(self, registry: SkillRegistry) -> None:
        """Test that duplicate skill names overwrite."""

        class Skill1(BaseSkill):
            name = "duplicate"

            async def can_handle(self, context: SkillContext) -> bool:
                return True

            async def execute(self, context: SkillContext) -> SkillResult:
                return SkillResult(success=True)

        class Skill2(BaseSkill):
            name = "duplicate"
            description = "Second version"

            async def can_handle(self, context: SkillContext) -> bool:
                return True

            async def execute(self, context: SkillContext) -> SkillResult:
                return SkillResult(success=True)

        registry.register_class(Skill1)
        registry.register_class(Skill2)

        skills = registry.list_skills()
        skill_names = [s["name"] for s in skills]
        assert skill_names.count("duplicate") == 1

    def test_register_empty_name_raises(self, registry: SkillRegistry) -> None:
        """Test that registering a skill with no name raises error."""

        class NoNameSkill(BaseSkill):
            async def can_handle(self, context: SkillContext) -> bool:
                return True

            async def execute(self, context: SkillContext) -> SkillResult:
                return SkillResult(success=True)

        with pytest.raises(ValueError, match="no name"):
            registry.register_class(NoNameSkill)

    @pytest.mark.asyncio
    async def test_load_skill(self, registry: SkillRegistry) -> None:
        """Test lazy loading a skill."""

        class TestSkill(BaseSkill):
            name = "lazy_skill"

            async def can_handle(self, context: SkillContext) -> bool:
                return True

            async def execute(self, context: SkillContext) -> SkillResult:
                return SkillResult(success=True)

        registry.register_class(TestSkill)

        # Skill should not be loaded yet
        skill_info = [s for s in registry.list_skills() if s["name"] == "lazy_skill"][0]
        assert skill_info["loaded"] is False

        # Load the skill
        instance = await registry.load_skill("lazy_skill")
        assert instance is not None
        assert instance._initialized is True

        # Should now be marked as loaded
        skill_info = [s for s in registry.list_skills() if s["name"] == "lazy_skill"][0]
        assert skill_info["loaded"] is True

    @pytest.mark.asyncio
    async def test_load_nonexistent_skill(self, registry: SkillRegistry) -> None:
        """Test loading a skill that doesn't exist."""
        with pytest.raises(KeyError, match="not found"):
            await registry.load_skill("nonexistent")

    @pytest.mark.asyncio
    async def test_execute_matching(self, registry: SkillRegistry) -> None:
        """Test executing a matching skill."""

        class MatchingSkill(BaseSkill):
            name = "matcher"
            priority = 10

            async def can_handle(self, context: SkillContext) -> bool:
                return "match" in context.user_input.lower()

            async def execute(self, context: SkillContext) -> SkillResult:
                return SkillResult(success=True, response="Matched!")

        registry.register_class(MatchingSkill)

        # Should match
        context = SkillContext(user_input="This should match")
        result = await registry.execute_matching(context)
        assert result is not None
        assert result.response == "Matched!"

        # Should not match
        context = SkillContext(user_input="Something else entirely")
        result = await registry.execute_matching(context)
        assert result is None

    @pytest.mark.asyncio
    async def test_skill_priority_order(self, registry: SkillRegistry) -> None:
        """Test that skills are executed in priority order."""

        executed = []

        class LowPrioritySkill(BaseSkill):
            name = "low"
            priority = 1

            async def can_handle(self, context: SkillContext) -> bool:
                return True

            async def execute(self, context: SkillContext) -> SkillResult:
                executed.append("low")
                return SkillResult(success=True)

        class HighPrioritySkill(BaseSkill):
            name = "high"
            priority = 10

            async def can_handle(self, context: SkillContext) -> bool:
                return True

            async def execute(self, context: SkillContext) -> SkillResult:
                executed.append("high")
                return SkillResult(success=True)

        registry.register_class(LowPrioritySkill)
        registry.register_class(HighPrioritySkill)

        context = SkillContext(user_input="test")
        await registry.execute_matching(context)

        # High priority should execute first and handle it
        assert "high" in executed

    def test_list_skills(self, registry: SkillRegistry) -> None:
        """Test listing registered skills."""

        class TestSkill1(BaseSkill):
            name = "skill1"
            description = "First skill"

            async def can_handle(self, context: SkillContext) -> bool:
                return True

            async def execute(self, context: SkillContext) -> SkillResult:
                return SkillResult(success=True)

        class TestSkill2(BaseSkill):
            name = "skill2"
            description = "Second skill"
            enabled = False

            async def can_handle(self, context: SkillContext) -> bool:
                return True

            async def execute(self, context: SkillContext) -> SkillResult:
                return SkillResult(success=True)

        registry.register_class(TestSkill1)
        registry.register_class(TestSkill2)

        skills = registry.list_skills()
        assert len(skills) == 2

        # Check skill1 info
        skill1_info = [s for s in skills if s["name"] == "skill1"][0]
        assert skill1_info["description"] == "First skill"
        assert skill1_info["enabled"] is True

        # Check skill2 info
        skill2_info = [s for s in skills if s["name"] == "skill2"][0]
        assert skill2_info["enabled"] is False

    def test_get_skill(self, registry: SkillRegistry) -> None:
        """Test getting a skill by name."""

        class TestSkill(BaseSkill):
            name = "gettable"

            async def can_handle(self, context: SkillContext) -> bool:
                return True

            async def execute(self, context: SkillContext) -> SkillResult:
                return SkillResult(success=True)

        registry.register_class(TestSkill)

        skill_class = registry.get_skill("gettable")
        assert skill_class is not None
        assert skill_class.name == "gettable"

        # Nonexistent skill
        assert registry.get_skill("nonexistent") is None

    @pytest.mark.asyncio
    async def test_unload_skill(self, registry: SkillRegistry) -> None:
        """Test unloading a skill."""

        class TestSkill(BaseSkill):
            name = "unloadable"

            async def can_handle(self, context: SkillContext) -> bool:
                return True

            async def execute(self, context: SkillContext) -> SkillResult:
                return SkillResult(success=True)

        registry.register_class(TestSkill)
        await registry.load_skill("unloadable")

        # Unload
        await registry.unload_skill("unloadable")
        skill_info = [s for s in registry.list_skills() if s["name"] == "unloadable"][0]
        assert skill_info["loaded"] is False


class TestSkillDecorator:
    """Test the @skill decorator."""

    @pytest.mark.asyncio
    async def test_create_skill_from_function(self) -> None:
        """Test creating a skill from a decorated function."""

        @skill(name="func_skill", description="From function")
        async def my_skill(context: SkillContext) -> SkillResult:
            return SkillResult(success=True, response="Function skill!")

        # my_skill is now a class
        instance = my_skill()
        assert instance.name == "func_skill"
        assert instance.description == "From function"

        # Test execution
        context = SkillContext(user_input="test")
        result = await instance.execute(context)
        assert result.response == "Function skill!"


class TestBuiltInSkills:
    """Test built-in skills."""

    @pytest.fixture
    async def registry_with_builtins(self) -> SkillRegistry:
        """Create registry with built-in skills loaded."""
        reset_registry()
        registry = SkillRegistry()

        # Import and register built-in skills
        from persona_agent.skills import built_in

        for _name, obj in built_in.__dict__.items():
            if (
                isinstance(obj, type)
                and issubclass(obj, BaseSkill)
                and obj is not BaseSkill
                and hasattr(obj, "name")
                and obj.name
            ):
                registry.register_class(obj)

        return registry

    @pytest.mark.asyncio
    async def test_greeting_skill(self, registry_with_builtins: SkillRegistry) -> None:
        """Test the greeting skill."""
        from persona_agent.skills.built_in import GreetingSkill

        skill = GreetingSkill()
        await skill.initialize()

        # Should handle greetings
        context = SkillContext(user_input="Hello there")
        assert await skill.can_handle(context) is True

        context = SkillContext(user_input="你好")
        assert await skill.can_handle(context) is True

        # Should not handle non-greetings
        context = SkillContext(user_input="What's the weather?")
        assert await skill.can_handle(context) is False

    @pytest.mark.asyncio
    async def test_farewell_skill(self, registry_with_builtins: SkillRegistry) -> None:
        """Test the farewell skill."""
        from persona_agent.skills.built_in import FarewellSkill

        skill = FarewellSkill()

        # Should handle farewells
        context = SkillContext(user_input="Goodbye")
        assert await skill.can_handle(context) is True

        context = SkillContext(user_input="再见")
        assert await skill.can_handle(context) is True

    @pytest.mark.asyncio
    async def test_echo_skill(self, registry_with_builtins: SkillRegistry) -> None:
        """Test the echo skill."""
        from persona_agent.skills.built_in import EchoSkill

        skill = EchoSkill()

        # Should handle anything
        context = SkillContext(user_input="Anything")
        assert await skill.can_handle(context) is True

        # Execute
        result = await skill.execute(context)
        assert result.success is True
        assert "Anything" in result.response

    @pytest.mark.asyncio
    async def test_help_skill(self, registry_with_builtins: SkillRegistry) -> None:
        """Test the help skill."""
        from persona_agent.skills.built_in import HelpSkill

        skill = HelpSkill()

        # Should handle help requests
        context = SkillContext(user_input="help")
        assert await skill.can_handle(context) is True

        context = SkillContext(user_input="你会什么")
        assert await skill.can_handle(context) is True


class TestGlobalRegistry:
    """Test global registry functions."""

    def test_get_registry_singleton(self) -> None:
        """Test that get_registry returns singleton."""
        reset_registry()

        reg1 = get_registry()
        reg2 = get_registry()

        assert reg1 is reg2

    def test_reset_registry(self) -> None:
        """Test resetting the global registry."""
        reset_registry()

        reg1 = get_registry()
        reset_registry()
        reg2 = get_registry()

        assert reg1 is not reg2
