"""Mood state schema definitions."""

import re
from pathlib import Path

from pydantic import BaseModel, Field


class MoodTransition(BaseModel):
    """A possible transition from one mood to another."""

    to: str
    triggers: list[str]
    probability: float = Field(0.5, ge=0.0, le=1.0)
    decay: int | None = None  # Seconds until natural decay


class MoodDefinition(BaseModel):
    """Definition of a mood state.

    Matches the user's mood_states.md format with:
    - Triggers (what activates this mood)
    - Core posture (how the character behaves)
    - Language style guidelines
    - Linked kaomoji and verbal tic categories
    """

    name: str
    display_name: str
    description: str
    triggers: list[str] = Field(default_factory=list)
    core_posture: str = ""
    language_style: str = ""
    linked_kaomoji_categories: list[str] = Field(default_factory=list)
    linked_verbal_tic_categories: list[str] = Field(default_factory=list)
    behaviors: list[str] = Field(default_factory=list)
    mixing_guidance: str = ""

    @classmethod
    def from_markdown(cls, path: Path) -> list["MoodDefinition"]:
        """Parse mood definitions from markdown file.

        Args:
            path: Path to the markdown file

        Returns:
            List of MoodDefinition instances
        """
        if not path.exists():
            raise FileNotFoundError(f"Mood states file not found: {path}")

        with open(path, encoding="utf-8") as f:
            content = f.read()

        moods = []

        # Parse markdown sections (## headers)
        # Pattern matches: ## 1. Name (Description) or ## Name: Description
        sections = re.split(r"\n##\s+", content)

        # Filter out empty sections and the content before first header
        sections = [s for s in sections if s.strip()]

        for section in sections:
            if not section.strip():
                continue

            mood = cls._parse_section(section)
            if mood:
                moods.append(mood)

        return moods

    @classmethod
    def _parse_section(cls, section: str) -> "MoodDefinition | None":
        """Parse a single markdown section into a MoodDefinition."""
        lines = section.strip().split("\n")
        if not lines:
            return None

        # First line is the header: "## Name (Description)" or similar
        header = lines[0].strip()

        # Extract name and description
        # Format: "Name (Description)" or "Name: Description"
        name_match = re.match(r"(.+?)[:：]\s*(.+)", header)
        if name_match:
            display_name = name_match.group(1).strip()
            description = name_match.group(2).strip()
        else:
            display_name = header
            description = ""

        # Generate a normalized name
        name = cls._normalize_name(display_name)

        # Parse other fields
        triggers = []
        core_posture = ""
        language_style = ""
        linked_kaomoji = []
        linked_tics = []
        behaviors = []
        mixing = ""

        current_field = None
        current_content = []

        def save_current_field():
            nonlocal current_field, current_content, triggers, core_posture, language_style, mixing
            if current_field == "triggers":
                triggers = current_content
            elif current_field == "core_posture":
                core_posture = "\n".join(current_content).strip()
            elif current_field == "language_style":
                language_style = "\n".join(current_content).strip()
            elif current_field == "mixing_guidance":
                mixing = "\n".join(current_content).strip()
            elif current_field == "behaviors":
                _behaviors = current_content  # Parsed for completeness

        for line in lines[1:]:
            line = line.strip()

            # Check for field headers
            if line.startswith("**触发器:**"):
                save_current_field()
                current_field = "triggers"
                trigger_text = line.replace("**触发器:**", "").strip()
                # Split comma-separated values
                current_content = [t.strip() for t in trigger_text.split(",") if t.strip()]
            elif line.startswith("**核心姿态:**"):
                save_current_field()
                current_field = "core_posture"
                posture_text = line.replace("**核心姿态:**", "").strip()
                current_content = [posture_text] if posture_text else []
            elif line.startswith("**语言风格:**"):
                save_current_field()
                current_field = "language_style"
                style_text = line.replace("**语言风格:**", "").strip()
                current_content = [style_text] if style_text else []
            elif line.startswith("**linked_knowledge:**"):
                save_current_field()
                current_field = "linked_knowledge"
                current_content = []
            elif line.startswith("**混合情绪指引:**"):
                save_current_field()
                current_field = "mixing_guidance"
                mixing_text = line.replace("**混合情绪指引:**", "").strip()
                current_content = [mixing_text] if mixing_text else []
            elif line.startswith("**行为特征:**"):
                save_current_field()
                current_field = "behaviors"
                current_content = []
            elif line.startswith("- ") and current_field:
                content = line[2:].strip()
                current_content.append(content)

                # Parse linked knowledge
                if current_field == "linked_knowledge":
                    if "Kaomoji:" in content or "颜文字:" in content:
                        # Extract kaomoji categories
                        match = re.search(r"(\w+_\w+|\w+)", content)
                        if match:
                            linked_kaomoji.append(match.group(1))
                    elif "口头禅:" in content:
                        # Extract verbal tic categories
                        match = re.search(r"(\w+)", content)
                        if match:
                            linked_tics.append(match.group(1))
            elif line and current_field:
                current_content.append(line)

        # Save the last field
        save_current_field()

        return cls(
            name=name,
            display_name=display_name,
            description=description,
            triggers=triggers,
            core_posture=core_posture,
            language_style=language_style,
            linked_kaomoji_categories=linked_kaomoji,
            linked_verbal_tic_categories=linked_tics,
            behaviors=behaviors,
            mixing_guidance=mixing,
        )

    @staticmethod
    def _normalize_name(display_name: str) -> str:
        """Convert display name to normalized name."""
        # Strip leading markdown headers
        display_name = display_name.lstrip("#").strip()

        # Extract English name if in format: "Name (Chinese)"
        match = re.match(r"([A-Z_]+)", display_name)
        if match:
            return match.group(1)

        # Convert Chinese to normalized form
        name_map = {
            "默认": "DEFAULT",
            "默认模式": "DEFAULT",
            "玩闹式挑逗": "PLAYFUL_TEASING",
            "高反差萌": "HIGH_CONTRAST_MOE",
            "核心反应": "HIGH_CONTRAST_MOE",
            "关切": "CARING",
            "关切保护": "CARING_PROTECTIVE",
            "好胜心": "COMPETITIVE",
            "占有欲": "POSSESSIVE",
            "嫉妒": "JEALOUS",
            "忧郁": "MELANCHOLY",
        }

        for key, value in name_map.items():
            if key in display_name:
                return value

        # Fallback: uppercase and replace spaces with underscores
        return re.sub(r"\s+", "_", display_name).upper()

    def to_prompt_modifier(self) -> str:
        """Convert mood to a prompt modifier string.

        Returns:
            Prompt modifier describing this mood
        """
        lines = [
            f"## 当前情绪: {self.display_name}",
            f"{self.description}",
            "",
            f"**姿态**: {self.core_posture}",
        ]

        if self.language_style:
            lines.append(f"**语言风格**: {self.language_style}")

        if self.behaviors:
            lines.append("**行为特征**:")
            for behavior in self.behaviors:
                lines.append(f"- {behavior}")

        return "\n".join(lines)


class MoodState(BaseModel):
    """Current mood state with metadata."""

    name: str
    intensity: float = Field(0.5, ge=0.0, le=1.0)
    entered_at: float = Field(default_factory=lambda: __import__("time").time())
    triggered_by: str | None = None

    def is_active(self, decay_seconds: float | None = None) -> bool:
        """Check if this mood state is still active.

        Args:
            decay_seconds: Optional decay time

        Returns:
            True if the mood is still active
        """
        if decay_seconds is None:
            return True

        import time

        elapsed = time.time() - self.entered_at
        return elapsed < decay_seconds
