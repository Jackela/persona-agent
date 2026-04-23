"""Skill evolution tracker.

This module provides the SkillEvolutionTracker class for recording
skill executions and tracking performance metrics over time.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from persona_agent.skills.evolution.models import (
    EvolutionConfig,
    SkillExecution,
    SkillMetrics,
)

if TYPE_CHECKING:
    from persona_agent.skills.base import SkillContext, SkillResult

logger = logging.getLogger(__name__)


class SkillEvolutionTracker:
    """Track skill executions and manage evolution metrics.

    This class records skill executions, maintains performance metrics,
    and determines when skills need improvement or can be evolved.

    Example:
        tracker = SkillEvolutionTracker()

        # Record an execution
        tracker.record_execution(
            skill_name="weather_skill",
            context=context,
            result=result,
            execution_time_ms=150,
        )

        # Check if skill needs improvement
        if tracker.needs_evolution("weather_skill"):
            metrics = tracker.get_metrics("weather_skill")
            print(f"Success rate: {metrics.success_rate:.1%}")
    """

    def __init__(self, config: EvolutionConfig | None = None) -> None:
        """Initialize the tracker.

        Args:
            config: Evolution configuration
        """
        self.config = config or EvolutionConfig()
        self._metrics: dict[str, SkillMetrics] = {}
        self._pending_proposals: dict[str, int] = {}  # skill_name -> count

    def record_execution(
        self,
        skill_name: str,
        context: SkillContext,
        result: SkillResult,
        execution_time_ms: int = 0,
    ) -> None:
        """Record a skill execution.

        Args:
            skill_name: Name of the skill
            context: Execution context
            result: Execution result
            execution_time_ms: Time taken to execute
        """
        if not self.config.enabled:
            return

        # Get or create metrics
        metrics = self._get_or_create_metrics(skill_name)

        # Create execution record
        execution = SkillExecution.create(
            skill_name=skill_name,
            input_summary=context.user_input[:200],
            success=result.success,
            execution_time_ms=execution_time_ms,
            user_feedback=result.data.get("user_feedback"),
            error_message=result.data.get("error") if not result.success else None,
            metadata={
                "confidence": result.confidence,
                "has_response": result.response is not None,
            },
        )

        # Update metrics
        metrics.record_execution(execution)

        logger.debug(
            f"Recorded execution for {skill_name}: "
            f"success={result.success}, time={execution_time_ms}ms"
        )

        # Check for auto-propose trigger
        if self.config.auto_propose and self._should_auto_propose(metrics):
            logger.info(f"Auto-propose triggered for {skill_name}")
            # This would typically trigger async proposal generation
            # For now, just log the suggestion

    def _get_or_create_metrics(self, skill_name: str) -> SkillMetrics:
        """Get existing metrics or create new."""
        if skill_name not in self._metrics:
            self._metrics[skill_name] = SkillMetrics(skill_name=skill_name)
        return self._metrics[skill_name]

    def _should_auto_propose(self, metrics: SkillMetrics) -> bool:
        """Determine if auto-propose should be triggered."""
        # Check minimum executions
        if metrics.total_executions < self.config.min_executions_before_evolution:
            return False

        # Check success rate
        if metrics.success_rate < self.config.success_rate_threshold:
            return True

        # Check pending proposals limit
        pending = self._pending_proposals.get(metrics.skill_name, 0)
        if pending >= self.config.max_proposals_per_skill:
            return False

        return False

    def get_metrics(self, skill_name: str) -> SkillMetrics | None:
        """Get metrics for a skill.

        Args:
            skill_name: Name of the skill

        Returns:
            SkillMetrics or None if no data
        """
        return self._metrics.get(skill_name)

    def get_all_metrics(self) -> dict[str, SkillMetrics]:
        """Get metrics for all tracked skills."""
        return self._metrics.copy()

    def needs_evolution(self, skill_name: str) -> bool:
        """Check if a skill needs evolution.

        Args:
            skill_name: Name of the skill

        Returns:
            True if skill needs improvement
        """
        metrics = self._metrics.get(skill_name)
        if not metrics:
            return False

        # Check minimum executions
        if metrics.total_executions < self.config.min_executions_before_evolution:
            return False

        return metrics.needs_improvement

    def get_skills_needing_evolution(self) -> list[str]:
        """Get list of skills that need evolution."""
        return [name for name, metrics in self._metrics.items() if self.needs_evolution(name)]

    def can_evolve(self, skill_name: str) -> bool:
        """Check if a skill can be evolved (has enough data)."""
        metrics = self._metrics.get(skill_name)
        if not metrics:
            return False

        return metrics.total_executions >= self.config.min_executions_before_evolution

    def get_recommended_mode(self, skill_name: str) -> str | None:
        """Get recommended evolution mode for a skill.

        Args:
            skill_name: Name of the skill

        Returns:
            Recommended mode ("fix", "derived", or None)
        """
        metrics = self._metrics.get(skill_name)
        if not metrics:
            return None

        if not self.can_evolve(skill_name):
            return None

        # If success rate is low, recommend FIX
        if metrics.success_rate < self.config.success_rate_threshold:
            return "fix"

        # If performing well, recommend DERIVED for optimization
        if metrics.is_performing_well:
            return "derived"

        return None

    def record_proposal_created(self, skill_name: str) -> None:
        """Record that a proposal was created for a skill."""
        self._pending_proposals[skill_name] = self._pending_proposals.get(skill_name, 0) + 1

    def record_proposal_resolved(self, skill_name: str) -> None:
        """Record that a proposal was resolved (approved/rejected)."""
        if skill_name in self._pending_proposals:
            self._pending_proposals[skill_name] = max(0, self._pending_proposals[skill_name] - 1)

    def get_pending_proposal_count(self, skill_name: str) -> int:
        """Get number of pending proposals for a skill."""
        return self._pending_proposals.get(skill_name, 0)

    def get_statistics(self) -> dict[str, Any]:
        """Get overall tracking statistics."""
        total_skills = len(self._metrics)
        skills_needing_evolution = len(self.get_skills_needing_evolution())
        well_performing_skills = sum(1 for m in self._metrics.values() if m.is_performing_well)
        total_executions = sum(m.total_executions for m in self._metrics.values())
        total_failures = sum(m.failed_executions for m in self._metrics.values())

        return {
            "total_skills_tracked": total_skills,
            "skills_needing_evolution": skills_needing_evolution,
            "well_performing_skills": well_performing_skills,
            "total_executions_recorded": total_executions,
            "total_failures": total_failures,
            "overall_success_rate": (
                (total_executions - total_failures) / total_executions
                if total_executions > 0
                else 0.0
            ),
        }

    def reset_metrics(self, skill_name: str) -> None:
        """Reset metrics for a skill (e.g., after evolution)."""
        if skill_name in self._metrics:
            del self._metrics[skill_name]
        logger.info(f"Reset metrics for {skill_name}")

    def clear_all(self) -> None:
        """Clear all tracked metrics."""
        self._metrics.clear()
        self._pending_proposals.clear()
        logger.info("Cleared all evolution tracking data")


__all__ = ["SkillEvolutionTracker"]
