"""Built-in skills for common tasks."""

import random
import re

from persona_agent.skills.base import BaseSkill, SkillContext, SkillResult


class EchoSkill(BaseSkill):
    """Simple echo skill for testing."""

    name = "echo"
    description = "Echo back the user's input"
    priority = -100  # Low priority, fallback

    async def can_handle(self, context: SkillContext) -> bool:
        """Always handle as fallback."""
        return True

    async def execute(self, context: SkillContext) -> SkillResult:
        """Echo the input."""
        return SkillResult(
            success=True,
            response=f"Echo: {context.user_input}",
            confidence=0.1,
        )


class GreetingSkill(BaseSkill):
    """Handle greeting messages."""

    name = "greeting"
    description = "Respond to greetings"
    priority = 10

    GREETING_PATTERNS = [
        r"^(hi|hello|hey|你好|您好|早上好|晚上好|好久不见)",
        r"^\\s*(在吗|在么|在不在)",
    ]

    RESPONSES = [
        "你好呀~ 有什么我可以帮你的吗？",
        "嗨！很高兴见到你",
        "你好！今天想聊些什么？",
        "在呢在呢~ 有什么我可以帮忙的吗？",
    ]

    async def can_handle(self, context: SkillContext) -> bool:
        """Check if input is a greeting."""
        text = context.user_input.lower().strip()
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in self.GREETING_PATTERNS)

    async def execute(self, context: SkillContext) -> SkillResult:
        """Return a greeting response."""
        response = random.choice(self.RESPONSES)

        # Add mood-specific touches if available
        if context.current_mood:
            if "moe" in context.current_mood.lower():
                response += " (◕‿◕✿)"
            elif "playful" in context.current_mood.lower():
                response += " 嘿嘿~"

        return SkillResult(
            success=True,
            response=response,
            confidence=0.9,
        )


class FarewellSkill(BaseSkill):
    """Handle farewell messages."""

    name = "farewell"
    description = "Respond to goodbyes"
    priority = 10

    FAREWELL_PATTERNS = [
        r"^(bye|goodbye|see you|再见|拜拜|晚安)",
        r"(我要走了|下次再聊|先走了)",
    ]

    RESPONSES = [
        "再见啦~ 记得想我哦！",
        "拜拜！期待下次见面~",
        "好的，慢走~ 随时欢迎回来聊天",
        "晚安！做个好梦 (◡‿◡✿)",
    ]

    async def can_handle(self, context: SkillContext) -> bool:
        """Check if input is a farewell."""
        text = context.user_input.lower().strip()
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in self.FAREWELL_PATTERNS)

    async def execute(self, context: SkillContext) -> SkillResult:
        """Return a farewell response."""
        return SkillResult(
            success=True,
            response=random.choice(self.RESPONSES),
            confidence=0.9,
        )


class WeatherSkill(BaseSkill):
    """Mock weather skill for demonstration."""

    name = "weather"
    description = "Get weather information"
    priority = 5

    WEATHER_PATTERNS = [
        r"(天气|weather|temperature|temperature|几度)",
        r"(下雨|rain|snow|下雪|晴天|sunny)",
    ]

    async def can_handle(self, context: SkillContext) -> bool:
        """Check if asking about weather."""
        text = context.user_input.lower()
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in self.WEATHER_PATTERNS)

    async def execute(self, context: SkillContext) -> SkillResult:
        """Return mock weather info."""
        # In real implementation, this would call a weather API
        responses = [
            "今天天气不错呢，适合出去走走~",
            "听说今天可能会下雨，记得带伞哦！",
            "天气有点热，注意多喝水防暑~",
            "是个晴朗的好天气呢！(☀️‿☀️)",
        ]

        return SkillResult(
            success=True,
            response=random.choice(responses),
            confidence=0.7,
            data={"mock": True},
        )


class MemoryRecallSkill(BaseSkill):
    """Skill to recall information from memory."""

    name = "memory_recall"
    description = "Recall past conversations and user preferences"
    priority = 3

    RECALL_PATTERNS = [
        r"(记得|以前|之前|上次|说过| recall|remember)",
        r"(我喜欢|我爱好|我的)",
    ]

    async def can_handle(self, context: SkillContext) -> bool:
        """Check if asking about past information."""
        text = context.user_input.lower()
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in self.RECALL_PATTERNS)

    async def execute(self, context: SkillContext) -> SkillResult:
        """Attempt to recall information."""
        if not context.memory_store or not context.user_id:
            return SkillResult(
                success=False,
                response="抱歉，我现在还不太记得呢...",
                confidence=0.3,
            )

        # In real implementation, query memory store
        # For now, return a placeholder
        return SkillResult(
            success=True,
            response="让我想想...我记得你之前提到过类似的事情呢~",
            confidence=0.5,
        )


class HelpSkill(BaseSkill):
    """Provide help information about available skills."""

    name = "help"
    description = "Show available skills and commands"
    priority = 20

    HELP_PATTERNS = [
        r"^(help|帮助|怎么用|能做什么|你会什么|功能)",
        r"\\?+$",
    ]

    async def can_handle(self, context: SkillContext) -> bool:
        """Check if asking for help."""
        text = context.user_input.lower().strip()
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in self.HELP_PATTERNS)

    async def execute(self, context: SkillContext) -> SkillResult:
        """Return help information."""
        from persona_agent.skills.registry import get_registry

        registry = get_registry()
        skills = registry.list_skills(include_unloaded=True)

        enabled_skills = [s for s in skills if s["enabled"]]

        skill_list = "\\n".join(
            f"• {s['name']}: {s['description']}" for s in enabled_skills[:10]  # Limit to first 10
        )

        response = f"""我可以帮你做这些事情哦：

{skill_list}

{"还有更多技能可用..." if len(enabled_skills) > 10 else ""}

有什么想聊的尽管告诉我吧~"""

        return SkillResult(
            success=True,
            response=response,
            confidence=0.95,
        )
