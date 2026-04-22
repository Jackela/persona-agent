"""Memory system configuration schemas.

This module defines the configuration structures for the hierarchical
memory system and memory compaction features.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class WorkingMemoryConfig(BaseModel):
    """Working memory (short-term) configuration.

    Attributes:
        max_exchanges: Maximum number of exchanges to keep in working memory
        ttl_seconds: Time-to-live for working memory entries
    """

    max_exchanges: int = Field(default=10, ge=5, le=50)
    ttl_seconds: int = Field(default=3600, ge=300, le=86400)


class EpisodicMemoryConfig(BaseModel):
    """Episodic memory configuration.

    Attributes:
        max_episodes: Maximum number of episodes to store
        auto_summarize_threshold: Number of episodes before auto-summarization
        storage_path: Path for episodic memory storage
    """

    max_episodes: int = Field(default=1000, ge=100, le=10000)
    auto_summarize_threshold: int = Field(default=50, ge=10, le=200)
    storage_path: str = "./data/memory/episodic"


class SemanticMemoryConfig(BaseModel):
    """Semantic memory configuration.

    Attributes:
        max_entities: Maximum number of entities to track
        max_facts_per_entity: Maximum facts per entity
        enable_relation_inference: Whether to infer relations automatically
    """

    max_entities: int = Field(default=500, ge=100, le=5000)
    max_facts_per_entity: int = Field(default=50, ge=10, le=200)
    enable_relation_inference: bool = True


class CompactionConfig(BaseModel):
    """Memory compaction configuration.

    Attributes:
        enabled: Whether automatic compaction is enabled
        older_than_days: Compact memories older than this many days
        schedule_hours: Hours between automatic compaction runs
        min_memories_to_compact: Minimum memories required before compacting
        summary_max_length: Maximum length of generated summaries
        llm_model: Model to use for summarization
    """

    enabled: bool = True
    older_than_days: int = Field(default=7, ge=1, le=90)
    schedule_hours: int = Field(default=24, ge=1, le=168)
    min_memories_to_compact: int = Field(default=10, ge=5, le=100)
    summary_max_length: int = Field(default=500, ge=100, le=2000)
    llm_model: str | None = None


class VectorMemoryConfig(BaseModel):
    """Vector memory configuration.

    Attributes:
        enabled: Whether vector memory is enabled
        storage_path: Path for vector storage
        embedding_model: Embedding model to use
        collection_name: ChromaDB collection name
        similarity_threshold: Minimum similarity for retrieval
        max_results: Maximum retrieval results
    """

    enabled: bool = True
    storage_path: str = "./data/memory/vector"
    embedding_model: str = "text-embedding-3-small"
    collection_name: str = "memory"
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    max_results: int = Field(default=5, ge=1, le=20)


class MemorySystemConfig(BaseModel):
    """Complete memory system configuration.

    This schema defines all configuration options for the hierarchical
    memory system, including compaction and vector storage.

    Example:
        ```yaml
        memory:
          working:
            max_exchanges: 10
            ttl_seconds: 3600
          episodic:
            max_episodes: 1000
            auto_summarize_threshold: 50
          compaction:
            enabled: true
            older_than_days: 7
            schedule_hours: 24
        ```
    """

    enabled: bool = True
    working: WorkingMemoryConfig = Field(default_factory=WorkingMemoryConfig)
    episodic: EpisodicMemoryConfig = Field(default_factory=EpisodicMemoryConfig)
    semantic: SemanticMemoryConfig = Field(default_factory=SemanticMemoryConfig)
    compaction: CompactionConfig = Field(default_factory=CompactionConfig)
    vector: VectorMemoryConfig = Field(default_factory=VectorMemoryConfig)

    @field_validator("working", mode="before")
    @classmethod
    def validate_working(cls, v: dict | WorkingMemoryConfig | None) -> WorkingMemoryConfig:
        """Handle both dict and object inputs."""
        if v is None:
            return WorkingMemoryConfig()
        if isinstance(v, WorkingMemoryConfig):
            return v
        return WorkingMemoryConfig(**v)

    @field_validator("episodic", mode="before")
    @classmethod
    def validate_episodic(cls, v: dict | EpisodicMemoryConfig | None) -> EpisodicMemoryConfig:
        """Handle both dict and object inputs."""
        if v is None:
            return EpisodicMemoryConfig()
        if isinstance(v, EpisodicMemoryConfig):
            return v
        return EpisodicMemoryConfig(**v)

    @field_validator("semantic", mode="before")
    @classmethod
    def validate_semantic(cls, v: dict | SemanticMemoryConfig | None) -> SemanticMemoryConfig:
        """Handle both dict and object inputs."""
        if v is None:
            return SemanticMemoryConfig()
        if isinstance(v, SemanticMemoryConfig):
            return v
        return SemanticMemoryConfig(**v)

    @field_validator("compaction", mode="before")
    @classmethod
    def validate_compaction(cls, v: dict | CompactionConfig | None) -> CompactionConfig:
        """Handle both dict and object inputs."""
        if v is None:
            return CompactionConfig()
        if isinstance(v, CompactionConfig):
            return v
        return CompactionConfig(**v)

    @field_validator("vector", mode="before")
    @classmethod
    def validate_vector(cls, v: dict | VectorMemoryConfig | None) -> VectorMemoryConfig:
        """Handle both dict and object inputs."""
        if v is None:
            return VectorMemoryConfig()
        if isinstance(v, VectorMemoryConfig):
            return v
        return VectorMemoryConfig(**v)


__all__ = [
    "MemorySystemConfig",
    "WorkingMemoryConfig",
    "EpisodicMemoryConfig",
    "SemanticMemoryConfig",
    "CompactionConfig",
    "VectorMemoryConfig",
]
