"""Character profile schema definitions."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class PhysicalProfile(BaseModel):
    """Physical characteristics of the character."""

    height: str | None = None
    figure: str | None = None
    hair: str | None = None
    eyes: str | None = None
    attire: dict[str, str] = Field(default_factory=dict)


class PersonalityTraits(BaseModel):
    """Big Five personality traits (0.0 - 1.0)."""

    openness: float = Field(0.5, ge=0.0, le=1.0)
    conscientiousness: float = Field(0.5, ge=0.0, le=1.0)
    extraversion: float = Field(0.5, ge=0.0, le=1.0)
    agreeableness: float = Field(0.5, ge=0.0, le=1.0)
    neuroticism: float = Field(0.5, ge=0.0, le=1.0)


class CommunicationStyle(BaseModel):
    """Communication style preferences."""

    tone: str = "friendly"  # friendly, professional, playful, serious
    verbosity: str = "medium"  # low, medium, high
    empathy: str = "medium"  # low, medium, high


class Traits(BaseModel):
    """Combined traits for the character."""

    personality: PersonalityTraits = Field(default_factory=PersonalityTraits)
    communication_style: CommunicationStyle = Field(default_factory=CommunicationStyle)


class Goals(BaseModel):
    """Character goals and objectives."""

    primary: str
    secondary: list[str] = Field(default_factory=list)


class PsychologicalDriver(BaseModel):
    """A psychological driver motivating character behavior."""

    principle: str
    methods: list[str] = Field(default_factory=list)
    manifestations: list[str] = Field(default_factory=list)
    strategies: list[str] = Field(default_factory=list)
    root_cause: str | None = None


class PsychologicalDrivers(BaseModel):
    """Character's psychological drivers."""

    drive_for_dominance: PsychologicalDriver | None = None
    drive_for_validation: PsychologicalDriver | None = None
    drive_for_security: PsychologicalDriver | None = None


class RelationshipArc(BaseModel):
    """A stage in the relationship development."""

    stage: int
    name: str
    description: str
    transition_to_next: str | None = None


class CharacterProfile(BaseModel):
    """Complete character profile definition.

    This schema matches the user's character_profile.yaml format,
    supporting complex persona definitions with psychological depth.
    """

    name: str
    version: str = "1.0.0"
    relationship: str | None = None

    # Physical characteristics
    physical: PhysicalProfile | None = None
    height: str | None = None  # Legacy support
    figure: str | None = None  # Legacy support
    hair: str | None = None  # Legacy support
    eyes: str | None = None  # Legacy support
    attire: dict[str, str] | None = None  # Legacy support

    # Psychological profile
    traits: Traits | None = None
    psychological_drivers: PsychologicalDrivers | None = None

    # Relationship dynamics
    relationship_arcs: list[RelationshipArc] = Field(default_factory=list)

    # Background and goals
    backstory: str = ""
    core_memories: list[str] = Field(default_factory=list)
    goals: Goals | None = None
    knowledge_domains: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    # Interactive elements
    interactive_hooks: list[str] = Field(default_factory=list)

    # Configuration references
    mood_config: str | None = None
    linguistic_style: str | None = None

    @field_validator("traits", mode="before")
    @classmethod
    def validate_traits(cls, v: Any) -> Traits | None:
        """Handle both dict and Traits objects."""
        if v is None:
            return None
        if isinstance(v, Traits):
            return v
        if isinstance(v, PersonalityTraits):
            return Traits(personality=v)
        return Traits(**v)

    @field_validator("goals", mode="before")
    @classmethod
    def validate_goals(cls, v: Any) -> Goals | None:
        """Handle both dict and Goals objects."""
        if v is None:
            return None
        if isinstance(v, Goals):
            return v
        if isinstance(v, dict):
            return Goals(**v)
        return Goals(primary=str(v))

    @classmethod
    def from_yaml(cls, path: Path) -> "CharacterProfile":
        """Load character profile from YAML file.

        Args:
            path: Path to the YAML configuration file

        Returns:
            CharacterProfile instance

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the YAML is invalid
        """
        if not path.exists():
            raise FileNotFoundError(f"Character profile not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # Handle legacy format where physical attributes are at root level
        if data:
            physical_attrs = {}
            for attr in ["height", "figure", "hair", "eyes", "attire"]:
                if attr in data and data[attr] is not None:
                    physical_attrs[attr] = data.pop(attr)

            if physical_attrs and "physical" not in data:
                data["physical"] = physical_attrs
            elif physical_attrs and "physical" in data and isinstance(data["physical"], dict):
                # Merge with existing physical data
                data["physical"].update(physical_attrs)

        return cls(**data)

    def to_prompt_context(self) -> str:
        """Convert profile to a system prompt context string.

        Returns:
            Formatted context string for LLM prompts
        """
        lines = [
            f"# 角色设定: {self.name}",
            "",
        ]

        if self.relationship:
            lines.append(f"**关系**: {self.relationship}")
            lines.append("")

        if self.physical:
            lines.append("## 外貌特征")
            if self.physical.height:
                lines.append(f"- 身高: {self.physical.height}")
            if self.physical.hair:
                lines.append(f"- 发型: {self.physical.hair}")
            if self.physical.eyes:
                lines.append(f"- 眼睛: {self.physical.eyes}")
            if self.physical.attire:
                for key, value in self.physical.attire.items():
                    lines.append(f"- {key}: {value}")
            lines.append("")

        if self.backstory:
            lines.append("## 背景故事")
            lines.append(self.backstory)
            lines.append("")

        if self.core_memories:
            lines.append("## 核心记忆")
            for memory in self.core_memories:
                lines.append(f"- {memory}")
            lines.append("")

        if self.goals:
            lines.append("## 目标")
            lines.append(f"**主要**: {self.goals.primary}")
            if self.goals.secondary:
                lines.append("**次要**:")
                for goal in self.goals.secondary:
                    lines.append(f"- {goal}")
            lines.append("")

        if self.psychological_drivers:
            lines.append("## 心理驱动力")
            if self.psychological_drivers.drive_for_dominance:
                lines.append("### 主导欲")
                driver = self.psychological_drivers.drive_for_dominance
                lines.append(f"{driver.principle}")
                if driver.methods:
                    lines.append(f"方法: {', '.join(driver.methods)}")
                lines.append("")

            if self.psychological_drivers.drive_for_validation:
                lines.append("### 认可需求")
                driver = self.psychological_drivers.drive_for_validation
                lines.append(f"{driver.principle}")
                lines.append("")

        return "\n".join(lines)
