"""Skill evolution configuration schemas.

This module defines the configuration structures for the skill evolution
system, including metrics tracking and proposal management.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class EvolutionModeConfig(BaseModel):
    """Configuration for specific evolution modes.

    Attributes:
        enabled: Whether this mode is enabled
        min_executions: Minimum executions before triggering
        auto_trigger: Whether to auto-trigger this mode
    """

    enabled: bool = True
    min_executions: int = Field(default=5, ge=3, le=50)
    auto_trigger: bool = False


class MetricsConfig(BaseModel):
    """Metrics tracking configuration.

    Attributes:
        max_history_size: Maximum execution history per skill
        track_execution_time: Whether to track execution timing
        track_user_feedback: Whether to track user feedback
        success_rate_window: Window size for success rate calculation
    """

    max_history_size: int = Field(default=100, ge=50, le=500)
    track_execution_time: bool = True
    track_user_feedback: bool = True
    success_rate_window: int = Field(default=50, ge=10, le=200)


class ProposalConfig(BaseModel):
    """Evolution proposal configuration.

    Attributes:
        max_proposals_per_skill: Maximum pending proposals per skill
        proposal_expiry_hours: Hours until proposals expire
        require_human_approval: Whether human approval is required
        auto_activate_approved: Whether to auto-activate approved proposals
    """

    max_proposals_per_skill: int = Field(default=3, ge=1, le=10)
    proposal_expiry_hours: float = Field(default=168.0, ge=24.0, le=720.0)
    require_human_approval: bool = True
    auto_activate_approved: bool = False


class LLMGenerationConfig(BaseModel):
    """LLM-based code generation configuration.

    Attributes:
        model: Model to use for code generation
        temperature: Temperature for generation
        max_tokens: Maximum tokens for generated code
        timeout_seconds: Timeout for generation requests
    """

    model: str | None = None
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    max_tokens: int = Field(default=4096, ge=1024, le=8192)
    timeout_seconds: int = Field(default=60, ge=10, le=300)


class SkillEvolutionConfig(BaseModel):
    """Complete skill evolution system configuration.

    This schema defines all configuration options for skill evolution,
    including metrics tracking, proposal management, and code generation.

    Example:
        ```yaml
        skill_evolution:
          enabled: true
          success_rate_threshold: 0.7
          modes:
            fix:
              enabled: true
              auto_trigger: false
            derived:
              enabled: true
              min_executions: 10
          proposals:
            max_proposals_per_skill: 3
            require_human_approval: true
        ```
    """

    enabled: bool = True
    success_rate_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    min_executions_before_evolution: int = Field(default=5, ge=3, le=50)
    storage_path: str = "./data/skill_evolution"

    modes: dict[str, EvolutionModeConfig] = Field(
        default_factory=lambda: {
            "fix": EvolutionModeConfig(enabled=True, min_executions=5, auto_trigger=False),
            "derived": EvolutionModeConfig(enabled=True, min_executions=10, auto_trigger=False),
            "captured": EvolutionModeConfig(enabled=True, min_executions=3, auto_trigger=False),
        }
    )

    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    proposals: ProposalConfig = Field(default_factory=ProposalConfig)
    llm_generation: LLMGenerationConfig = Field(default_factory=LLMGenerationConfig)

    @field_validator("success_rate_threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        """Ensure threshold is valid."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("success_rate_threshold must be between 0.0 and 1.0")
        return v

    @field_validator("modes", mode="before")
    @classmethod
    def validate_modes(cls, v: dict | None) -> dict[str, EvolutionModeConfig]:
        """Handle both dict and object inputs."""
        if v is None:
            return {
                "fix": EvolutionModeConfig(),
                "derived": EvolutionModeConfig(),
                "captured": EvolutionModeConfig(),
            }

        result = {}
        for mode_name, mode_config in v.items():
            if isinstance(mode_config, EvolutionModeConfig):
                result[mode_name] = mode_config
            else:
                result[mode_name] = EvolutionModeConfig(**mode_config)

        # Ensure all modes have defaults
        for mode in ["fix", "derived", "captured"]:
            if mode not in result:
                result[mode] = EvolutionModeConfig()

        return result

    @field_validator("metrics", mode="before")
    @classmethod
    def validate_metrics(cls, v: dict | MetricsConfig | None) -> MetricsConfig:
        """Handle both dict and object inputs."""
        if v is None:
            return MetricsConfig()
        if isinstance(v, MetricsConfig):
            return v
        return MetricsConfig(**v)

    @field_validator("proposals", mode="before")
    @classmethod
    def validate_proposals(cls, v: dict | ProposalConfig | None) -> ProposalConfig:
        """Handle both dict and object inputs."""
        if v is None:
            return ProposalConfig()
        if isinstance(v, ProposalConfig):
            return v
        return ProposalConfig(**v)

    @field_validator("llm_generation", mode="before")
    @classmethod
    def validate_llm_generation(cls, v: dict | LLMGenerationConfig | None) -> LLMGenerationConfig:
        """Handle both dict and object inputs."""
        if v is None:
            return LLMGenerationConfig()
        if isinstance(v, LLMGenerationConfig):
            return v
        return LLMGenerationConfig(**v)


__all__ = [
    "SkillEvolutionConfig",
    "EvolutionModeConfig",
    "MetricsConfig",
    "ProposalConfig",
    "LLMGenerationConfig",
]
