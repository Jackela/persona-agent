"""Data models for skill evolution.

This module defines the core data structures used by the evolution system,
including evolution modes, metrics, proposals, and configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class EvolutionMode(Enum):
    """Enumeration of skill evolution modes.

    FIX: Repair a buggy skill by fixing errors
    DERIVED: Create an improved variant based on successful patterns
    CAPTURED: Learn a new skill from conversation examples
    """

    FIX = "fix"
    DERIVED = "derived"
    CAPTURED = "captured"

    @classmethod
    def from_string(cls, value: str) -> EvolutionMode:
        """Create mode from string value."""
        try:
            return cls(value.lower())
        except ValueError as e:
            raise ValueError(f"Invalid evolution mode: {value}") from e


class ProposalStatus(Enum):
    """Status of an evolution proposal."""

    PENDING = "pending"  # Awaiting review
    APPROVED = "approved"  # Approved and activated
    REJECTED = "rejected"  # Rejected
    EXPIRED = "expired"  # Expired without review


@dataclass
class SkillExecution:
    """Record of a single skill execution.

    Attributes:
        skill_name: Name of the executed skill
        timestamp: When the execution occurred
        input_summary: Brief summary of the input
        success: Whether execution succeeded
        execution_time_ms: Time taken in milliseconds
        user_feedback: Optional user feedback
        error_message: Error message if failed
        metadata: Additional execution metadata
    """

    skill_name: str
    timestamp: datetime
    input_summary: str
    success: bool
    execution_time_ms: int = 0
    user_feedback: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure timestamp is timezone-aware."""
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=UTC)

    @classmethod
    def create(
        cls,
        skill_name: str,
        input_summary: str,
        success: bool,
        **kwargs: Any,
    ) -> SkillExecution:
        """Create a new execution record with current timestamp."""
        return cls(
            skill_name=skill_name,
            timestamp=datetime.now(UTC),
            input_summary=input_summary,
            success=success,
            **kwargs,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "skill_name": self.skill_name,
            "timestamp": self.timestamp.isoformat(),
            "input_summary": self.input_summary,
            "success": self.success,
            "execution_time_ms": self.execution_time_ms,
            "user_feedback": self.user_feedback,
            "error_message": self.error_message,
            "metadata": self.metadata.copy(),
        }


@dataclass
class SkillMetrics:
    """Aggregated metrics for a skill.

    Tracks execution statistics and provides insights into
    skill performance and improvement opportunities.
    """

    skill_name: str
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_execution_time_ms: int = 0
    last_execution: datetime | None = None
    common_errors: dict[str, int] = field(default_factory=dict)
    execution_history: list[SkillExecution] = field(default_factory=list)
    max_history_size: int = 100

    @property
    def success_rate(self) -> float:
        """Calculate success rate (0.0 to 1.0)."""
        if self.total_executions == 0:
            return 0.0
        return self.successful_executions / self.total_executions

    @property
    def average_execution_time_ms(self) -> float:
        """Calculate average execution time."""
        if self.total_executions == 0:
            return 0.0
        return self.total_execution_time_ms / self.total_executions

    @property
    def needs_improvement(self) -> bool:
        """Determine if skill needs improvement.

        Returns True if:
        - Success rate is below threshold after minimum executions
        - Multiple different errors are occurring
        """
        if self.total_executions < 5:
            return False  # Not enough data

        return self.success_rate < 0.7 or len(self.common_errors) > 2

    @property
    def is_performing_well(self) -> bool:
        """Check if skill is performing well."""
        return self.total_executions >= 10 and self.success_rate >= 0.9

    def record_execution(self, execution: SkillExecution) -> None:
        """Record an execution and update metrics."""
        self.total_executions += 1
        self.last_execution = execution.timestamp

        if execution.success:
            self.successful_executions += 1
        else:
            self.failed_executions += 1
            if execution.error_message:
                # Track error frequency
                error_key = execution.error_message[:100]  # Truncate for grouping
                self.common_errors[error_key] = self.common_errors.get(error_key, 0) + 1

        self.total_execution_time_ms += execution.execution_time_ms

        # Add to history (maintain max size)
        self.execution_history.append(execution)
        if len(self.execution_history) > self.max_history_size:
            self.execution_history.pop(0)

    def get_recent_errors(self, count: int = 5) -> list[str]:
        """Get recent error messages."""
        errors = [
            ex.error_message
            for ex in reversed(self.execution_history)
            if not ex.success and ex.error_message
        ]
        return errors[:count]

    def get_top_errors(self, count: int = 3) -> list[tuple[str, int]]:
        """Get most frequent errors with counts."""
        sorted_errors = sorted(
            self.common_errors.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return sorted_errors[:count]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "skill_name": self.skill_name,
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "success_rate": self.success_rate,
            "average_execution_time_ms": self.average_execution_time_ms,
            "needs_improvement": self.needs_improvement,
            "is_performing_well": self.is_performing_well,
            "common_errors": self.common_errors.copy(),
            "last_execution": self.last_execution.isoformat() if self.last_execution else None,
        }


@dataclass
class EvolutionProposal:
    """A proposal for skill evolution.

    Represents a suggested improvement to a skill, including
    the new code, reasoning, and metadata for review.
    """

    id: str
    skill_name: str
    mode: EvolutionMode
    original_code: str
    proposed_code: str
    reasoning: str
    created_at: datetime
    status: ProposalStatus = ProposalStatus.PENDING
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None
    rejection_reason: str | None = None
    metrics_at_creation: dict[str, Any] = field(default_factory=dict)
    parent_proposal_id: str | None = None

    def __post_init__(self):
        """Ensure timestamp is timezone-aware."""
        if self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=UTC)

    @property
    def is_pending(self) -> bool:
        """Check if proposal is pending review."""
        return self.status == ProposalStatus.PENDING

    @property
    def age_hours(self) -> float:
        """Calculate age in hours."""
        delta = datetime.now(UTC) - self.created_at
        return delta.total_seconds() / 3600

    def approve(self, reviewed_by: str) -> None:
        """Mark proposal as approved."""
        self.status = ProposalStatus.APPROVED
        self.reviewed_at = datetime.now(UTC)
        self.reviewed_by = reviewed_by

    def reject(self, reason: str, reviewed_by: str) -> None:
        """Mark proposal as rejected."""
        self.status = ProposalStatus.REJECTED
        self.rejection_reason = reason
        self.reviewed_at = datetime.now(UTC)
        self.reviewed_by = reviewed_by

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "skill_name": self.skill_name,
            "mode": self.mode.value,
            "reasoning": self.reasoning,
            "created_at": self.created_at.isoformat(),
            "status": self.status.value,
            "is_pending": self.is_pending,
            "age_hours": self.age_hours,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewed_by": self.reviewed_by,
            "rejection_reason": self.rejection_reason,
            "parent_proposal_id": self.parent_proposal_id,
        }


@dataclass
class EvolutionConfig:
    """Configuration for skill evolution.

    Attributes:
        enabled: Whether evolution is enabled
        min_executions_before_evolution: Minimum executions before considering evolution
        success_rate_threshold: Below this, trigger FIX mode
        auto_propose: Automatically generate proposals without manual trigger
        require_human_approval: Whether human approval is required
        max_proposals_per_skill: Maximum pending proposals per skill
        proposal_expiry_hours: Hours until pending proposals expire
        storage_path: Path for storing evolution data
    """

    enabled: bool = True
    min_executions_before_evolution: int = 5
    success_rate_threshold: float = 0.7
    auto_propose: bool = False
    require_human_approval: bool = True
    max_proposals_per_skill: int = 3
    proposal_expiry_hours: float = 168.0  # 7 days
    storage_path: str = "./data/skill_evolution"

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.min_executions_before_evolution < 3:
            raise ValueError("min_executions_before_evolution must be at least 3")
        if not 0.0 <= self.success_rate_threshold <= 1.0:
            raise ValueError("success_rate_threshold must be between 0.0 and 1.0")
        if self.max_proposals_per_skill < 1:
            raise ValueError("max_proposals_per_skill must be at least 1")


__all__ = [
    "EvolutionMode",
    "ProposalStatus",
    "SkillExecution",
    "SkillMetrics",
    "EvolutionProposal",
    "EvolutionConfig",
]
