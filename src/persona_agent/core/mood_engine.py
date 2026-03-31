"""Mood engine for persona-agent.

Manages emotional state transitions and provides prompt modifiers
based on the character's current mood.
"""

import logging
import random
import time
from pathlib import Path
from typing import Any

from persona_agent.config.schemas.mood import MoodDefinition, MoodState

logger = logging.getLogger(__name__)


class MoodEngine:
    """Emotional state management engine.

    Tracks the character's current mood and handles transitions
    based on user input and context.
    """

    # Default moods if no config provided
    DEFAULT_MOODS = {
        "DEFAULT": {
            "display_name": "默认",
            "description": "日常互动状态",
            "triggers": ["日常互动"],
            "core_posture": "平衡且乐于助人",
            "language_style": "清晰简洁",
        },
        "PLAYFUL": {
            "display_name": "玩闹",
            "description": "轻松愉快的状态",
            "triggers": ["玩笑", "轻松话题"],
            "core_posture": "活泼好动",
            "language_style": "幽默风趣",
        },
        "CARING": {
            "display_name": "关切",
            "description": "关心支持的状态",
            "triggers": ["负面情绪", "需要帮助"],
            "core_posture": "温柔体贴",
            "language_style": "温暖安慰",
        },
    }

    def __init__(
        self,
        mood_definitions: list[MoodDefinition] | None = None,
        default_mood: str = "DEFAULT",
    ):
        """Initialize mood engine.

        Args:
            mood_definitions: List of mood definitions
            default_mood: Default mood name
        """
        self.moods: dict[str, MoodDefinition] = {}
        self.current_state: MoodState
        self.history: list[tuple[str, float, str]] = []  # (mood, timestamp, trigger)

        # Load mood definitions
        if mood_definitions:
            for mood in mood_definitions:
                self.moods[mood.name] = mood
        else:
            # Use default moods
            for name, data in self.DEFAULT_MOODS.items():
                self.moods[name] = MoodDefinition(name=name, **data)

        # Set initial state
        self.current_state = MoodState(
            name=default_mood if default_mood in self.moods else "DEFAULT",
            intensity=0.5,
        )

        logger.debug(f"MoodEngine initialized with {len(self.moods)} moods")

    @classmethod
    def from_config(cls, config_path: Path) -> "MoodEngine":
        """Load mood engine from configuration file.

        Args:
            config_path: Path to mood states markdown file

        Returns:
            Configured MoodEngine instance
        """
        moods = MoodDefinition.from_markdown(config_path)
        return cls(mood_definitions=moods)

    def update(self, trigger: str, context: dict[str, Any] | None = None) -> MoodState:
        """Update mood based on trigger.

        Args:
            trigger: The triggering event/input
            context: Additional context

        Returns:
            Updated mood state
        """
        context = context or {}
        current_mood = self.current_state.name

        # Check for mood transitions
        # Simple rule-based system - can be enhanced with LLM
        new_mood = self._evaluate_transition(trigger, current_mood, context)

        if new_mood != current_mood:
            # Record transition
            self.history.append((current_mood, time.time(), trigger))

            # Create new state
            self.current_state = MoodState(
                name=new_mood,
                intensity=self._calculate_intensity(new_mood, trigger),
                triggered_by=trigger,
            )

            logger.debug(f"Mood transition: {current_mood} -> {new_mood} (trigger: {trigger})")

        return self.current_state

    def _evaluate_transition(
        self,
        trigger: str,
        current_mood: str,
        context: dict[str, Any],
    ) -> str:
        """Evaluate if mood should transition.

        Args:
            trigger: Triggering event
            current_mood: Current mood name
            context: Context dict

        Returns:
            New mood name (may be same as current)
        """
        trigger_lower = trigger.lower()

        # Check each mood's triggers
        for mood_name, mood_def in self.moods.items():
            for mood_trigger in mood_def.triggers:
                if mood_trigger.lower() in trigger_lower:
                    # Found a matching trigger
                    if mood_name != current_mood:
                        return mood_name

        # Keyword-based heuristics for user's specific moods
        negative_words = [
            "难过",
            "伤心",
            "痛苦",
            "累",
            "不舒服",
            "sad",
            "upset",
            "depressed",
            "hurt",
            "tired",
        ]
        if any(word in trigger_lower for word in negative_words):
            # User expressing negative emotions -> Caring mode
            if "CARING_PROTECTIVE" in self.moods:
                return "CARING_PROTECTIVE"
            if "CARING" in self.moods:
                return "CARING"

        if any(
            word in trigger_lower
            for word in ["赢", "胜利", "打败", "成功", "win", "won", "victory", "success"]
        ):
            # Victory situation -> Competitive/Victorious mode
            if "COMPETITIVE" in self.moods:
                return "COMPETITIVE"

        if any(word in trigger_lower for word in ["夸", "赞", "好棒", "厉害", "聪明"]):
            # User praising -> Can trigger high-contrast moe
            if random.random() < 0.3:  # 30% chance
                if "HIGH_CONTRAST_MOE" in self.moods:
                    return "HIGH_CONTRAST_MOE"

        if any(word in trigger_lower for word in ["别的", "其他", "她", "他", "别人"]):
            # Mentioning others -> Jealousy mode
            if "JEALOUS" in self.moods:
                return "JEALOUS"

        # Check for mood decay (return to default)
        current_time = time.time()
        entered_time = self.current_state.entered_at
        elapsed = current_time - entered_time

        # Most moods decay after some time (except default)
        if current_mood != "DEFAULT" and elapsed > 300:  # 5 minutes
            decay_probability = min(0.7, elapsed / 600)  # Max 70% after 10 min
            if random.random() < decay_probability:
                return "DEFAULT"

        return current_mood

    def _calculate_intensity(self, mood: str, trigger: str) -> float:
        """Calculate mood intensity based on trigger.

        Args:
            mood: Mood name
            trigger: Trigger string

        Returns:
            Intensity value 0.0-1.0
        """
        # Base intensity
        base = 0.5

        # Adjust based on trigger strength
        strong_words = ["非常", "特别", "超级", "真的", "very", "really", "so", "extremely"]
        if any(word in trigger.lower() for word in strong_words):
            base += 0.2

        weak_words = ["有点", "稍微", "略", "a bit", "slightly", "little"]
        if any(word in trigger.lower() for word in weak_words):
            base -= 0.1

        # Some moods are naturally more intense
        intense_moods = ["HIGH_CONTRAST_MOE", "COMPETITIVE", "JEALOUS"]
        if mood in intense_moods:
            base += 0.1

        return max(0.0, min(1.0, base))

    def get_current_mood(self) -> MoodDefinition | None:
        """Get current mood definition.

        Returns:
            Current mood definition or None
        """
        return self.moods.get(self.current_state.name)

    def get_prompt_modifier(self) -> str:
        """Get prompt modifier for current mood.

        Returns:
            Prompt modifier string
        """
        mood = self.get_current_mood()
        if not mood:
            return ""

        lines = [
            f"## 当前情绪状态: {mood.display_name}",
            f"**描述**: {mood.description}",
        ]

        if mood.core_posture:
            lines.append(f"**姿态**: {mood.core_posture}")

        if mood.language_style:
            lines.append(f"**语言风格**: {mood.language_style}")

        lines.append(f"**强度**: {self.current_state.intensity:.1%}")

        return "\n".join(lines)

    def get_kaomoji_categories(self) -> list[str]:
        """Get recommended kaomoji categories for current mood.

        Returns:
            List of category names
        """
        mood = self.get_current_mood()
        if not mood:
            return ["default_triumphant"]

        categories = mood.linked_kaomoji_categories
        if not categories:
            # Default mappings
            mood_category_map = {
                "DEFAULT": ["default_triumphant", "default_teasing"],
                "PLAYFUL_TEASING": ["default_triumphant", "default_teasing"],
                "HIGH_CONTRAST_MOE": ["moe_panic", "moe_shy", "moe_tsundere"],
                "CARING_PROTECTIVE": ["caring_gentle", "caring_tsundere"],
                "COMPETITIVE": ["competitive_showoff"],
                "JEALOUS": ["jealousy_sulking"],
                "MELANCHOLY": ["melancholy_calm"],
            }
            categories = mood_category_map.get(self.current_state.name, ["default_triumphant"])

        return categories

    def get_verbal_tic_categories(self) -> list[str]:
        """Get recommended verbal tic categories for current mood.

        Returns:
            List of category names
        """
        mood = self.get_current_mood()
        if not mood:
            return ["teasing"]

        categories = mood.linked_verbal_tic_categories
        if not categories:
            # Default mappings
            mood_tic_map = {
                "DEFAULT": ["teasing"],
                "PLAYFUL_TEASING": ["triumphant", "teasing"],
                "HIGH_CONTRAST_MOE": ["shy"],
                "CARING_PROTECTIVE": ["caring"],
                "COMPETITIVE": ["triumphant"],
                "JEALOUS": ["teasing"],
                "MELANCHOLY": [],
            }
            categories = mood_tic_map.get(self.current_state.name, ["teasing"])

        return categories
