"""Application settings schema.

This module defines the main application settings that combines
all subsystem configurations into a unified structure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

from persona_agent.config.schemas.evolution import SkillEvolutionConfig
from persona_agent.config.schemas.memory import MemorySystemConfig
from persona_agent.config.schemas.planning import PlanningSystemConfig


class LLMConfig(BaseModel):
    """LLM provider configuration.

    Attributes:
        provider: LLM provider (openai, anthropic, local)
        model: Model name
        api_key: API key (optional, can use env var)
        base_url: Custom base URL for API
        timeout_seconds: Request timeout
        max_retries: Maximum retry attempts
    """

    provider: str = Field(default="openai", pattern=r"^(openai|anthropic|local)$")
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    timeout_seconds: int = Field(default=60, ge=10, le=300)
    max_retries: int = Field(default=3, ge=0, le=10)


class LoggingConfig(BaseModel):
    """Logging configuration.

    Attributes:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        format: Log format string
        file: Optional log file path
        max_bytes: Maximum log file size
        backup_count: Number of backup files to keep
    """

    level: str = Field(default="INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: str | None = None
    max_bytes: int = Field(default=10_000_000, ge=1_000_000)
    backup_count: int = Field(default=5, ge=0, le=20)


class DatabaseConfig(BaseModel):
    """Database configuration.

    Attributes:
        url: Database URL or path
        pool_size: Connection pool size
        max_overflow: Maximum overflow connections
        echo: Whether to echo SQL statements
    """

    url: str = "sqlite:///data/persona_agent.db"
    pool_size: int = Field(default=5, ge=1, le=20)
    max_overflow: int = Field(default=10, ge=0, le=50)
    echo: bool = False


class SessionConfig(BaseModel):
    """Session management configuration.

    Attributes:
        ttl_hours: Session time-to-live in hours
        max_messages: Maximum messages per session
        auto_save: Whether to auto-save sessions
    """

    ttl_hours: int = Field(default=168, ge=1, le=720)  # 7 days default
    max_messages: int = Field(default=1000, ge=100, le=10000)
    auto_save: bool = True


class ApplicationSettings(BaseModel):
    """Complete application settings.

    This is the root configuration structure that combines all
    subsystem configurations into a single, loadable settings object.

    Example:
        ```yaml
        app:
          name: "Persona Agent"
          version: "0.2.0"

        llm:
          provider: openai
          model: gpt-4o-mini

        planning:
          enabled: true
          execution:
            enable_parallel_execution: true

        memory:
          enabled: true
          compaction:
            enabled: true
            older_than_days: 7

        skill_evolution:
          enabled: true
          success_rate_threshold: 0.7
        ```
    """

    # Application metadata
    app_name: str = Field(default="Persona Agent", alias="app.name")
    app_version: str = Field(default="0.2.0", alias="app.version")
    debug: bool = Field(default=False, alias="app.debug")

    # Subsystem configurations
    llm: LLMConfig = Field(default_factory=LLMConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)

    # New subsystem configurations
    planning: PlanningSystemConfig = Field(default_factory=PlanningSystemConfig)
    memory: MemorySystemConfig = Field(default_factory=MemorySystemConfig)
    skill_evolution: SkillEvolutionConfig = Field(
        default_factory=SkillEvolutionConfig, alias="skill_evolution"
    )

    @field_validator("llm", mode="before")
    @classmethod
    def validate_llm(cls, v: dict | LLMConfig | None) -> LLMConfig:
        """Handle both dict and object inputs."""
        if v is None:
            return LLMConfig()
        if isinstance(v, LLMConfig):
            return v
        return LLMConfig(**v)

    @field_validator("database", mode="before")
    @classmethod
    def validate_database(cls, v: dict | DatabaseConfig | None) -> DatabaseConfig:
        """Handle both dict and object inputs."""
        if v is None:
            return DatabaseConfig()
        if isinstance(v, DatabaseConfig):
            return v
        return DatabaseConfig(**v)

    @field_validator("logging", mode="before")
    @classmethod
    def validate_logging(cls, v: dict | LoggingConfig | None) -> LoggingConfig:
        """Handle both dict and object inputs."""
        if v is None:
            return LoggingConfig()
        if isinstance(v, LoggingConfig):
            return v
        return LoggingConfig(**v)

    @field_validator("session", mode="before")
    @classmethod
    def validate_session(cls, v: dict | SessionConfig | None) -> SessionConfig:
        """Handle both dict and object inputs."""
        if v is None:
            return SessionConfig()
        if isinstance(v, SessionConfig):
            return v
        return SessionConfig(**v)

    @field_validator("planning", mode="before")
    @classmethod
    def validate_planning(
        cls, v: dict | PlanningSystemConfig | None
    ) -> PlanningSystemConfig:
        """Handle both dict and object inputs."""
        if v is None:
            return PlanningSystemConfig()
        if isinstance(v, PlanningSystemConfig):
            return v
        return PlanningSystemConfig(**v)

    @field_validator("memory", mode="before")
    @classmethod
    def validate_memory(cls, v: dict | MemorySystemConfig | None) -> MemorySystemConfig:
        """Handle both dict and object inputs."""
        if v is None:
            return MemorySystemConfig()
        if isinstance(v, MemorySystemConfig):
            return v
        return MemorySystemConfig(**v)

    @field_validator("skill_evolution", mode="before")
    @classmethod
    def validate_skill_evolution(
        cls, v: dict | SkillEvolutionConfig | None
    ) -> SkillEvolutionConfig:
        """Handle both dict and object inputs."""
        if v is None:
            return SkillEvolutionConfig()
        if isinstance(v, SkillEvolutionConfig):
            return v
        return SkillEvolutionConfig(**v)

    @classmethod
    def from_yaml(cls, path: Path) -> ApplicationSettings:
        """Load settings from YAML file.

        Args:
            path: Path to the YAML configuration file

        Returns:
            ApplicationSettings instance

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the YAML is invalid
        """
        if not path.exists():
            raise FileNotFoundError(f"Settings file not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # Handle flat or nested structure
        flattened = cls._flatten_dict(data or {})

        return cls(**flattened)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApplicationSettings:
        """Create settings from dictionary.

        Args:
            data: Configuration dictionary

        Returns:
            ApplicationSettings instance
        """
        flattened = cls._flatten_dict(data)
        return cls(**flattened)

    @staticmethod
    def _flatten_dict(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
        """Flatten nested dictionary with dot notation keys.

        Args:
            data: Nested dictionary
            prefix: Key prefix for recursion

        Returns:
            Flattened dictionary
        """
        result = {}
        for key, value in data.items():
            new_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict) and not isinstance(value, (str, bytes)):
                # Check if this is a subsystem config (has its own validator)
                subsystem_keys = [
                    "llm", "database", "logging", "session",
                    "planning", "memory", "skill_evolution"
                ]
                if key in subsystem_keys:
                    result[key] = value
                elif key == "app":
                    # Flatten app config
                    result.update(ApplicationSettings._flatten_dict(value, "app"))
                else:
                    result[new_key] = value
            else:
                result[new_key] = value

        return result

    def to_yaml(self, path: Path | None = None) -> str:
        """Convert settings to YAML string.

        Args:
            path: Optional path to write YAML file

        Returns:
            YAML string representation
        """
        data = self.model_dump(by_alias=True, exclude_none=True)

        # Convert to nested structure
        nested = self._nest_dict(data)

        yaml_str = yaml.dump(nested, default_flow_style=False, sort_keys=True, allow_unicode=True)

        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(yaml_str)

        return yaml_str

    @staticmethod
    def _nest_dict(data: dict[str, Any]) -> dict[str, Any]:
        """Convert flat dictionary to nested structure.

        Args:
            data: Flat dictionary with dot notation keys

        Returns:
            Nested dictionary
        """
        result = {}

        for key, value in data.items():
            if "." in key:
                parts = key.split(".")
                current = result
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                current[parts[-1]] = value
            else:
                result[key] = value

        return result

    def get_planning_config(self) -> PlanningSystemConfig:
        """Get planning system configuration."""
        return self.planning

    def get_memory_config(self) -> MemorySystemConfig:
        """Get memory system configuration."""
        return self.memory

    def get_skill_evolution_config(self) -> SkillEvolutionConfig:
        """Get skill evolution configuration."""
        return self.skill_evolution


__all__ = [
    "ApplicationSettings",
    "LLMConfig",
    "LoggingConfig",
    "DatabaseConfig",
    "SessionConfig",
]
