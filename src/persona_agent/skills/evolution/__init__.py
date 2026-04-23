"""Skill evolution system for self-improving skills.

This module provides capabilities for skills to evolve and improve over time
based on execution feedback and performance metrics.

The evolution system supports three modes:
- FIX: Repair buggy skills
- DERIVED: Create improved variants based on successful patterns
- CAPTURED: Learn new skills from conversation examples

Example:
    from persona_agent.skills.evolution import SkillEvolutionTracker

    tracker = SkillEvolutionTracker()
    tracker.record_execution("weather_skill", context, result)

    if tracker.needs_evolution("weather_skill"):
        proposal = await tracker.generate_evolution("weather_skill", EvolutionMode.FIX)
"""

from persona_agent.skills.evolution.exceptions import (
    EvolutionError,
    GenerationError,
    InvalidEvolutionModeError,
    ProposalError,
)
from persona_agent.skills.evolution.generator import EvolutionGenerator
from persona_agent.skills.evolution.manager import EvolutionManager, ProposalStatus
from persona_agent.skills.evolution.models import (
    EvolutionConfig,
    EvolutionMode,
    EvolutionProposal,
    SkillMetrics,
)
from persona_agent.skills.evolution.tracker import SkillEvolutionTracker

__version__ = "1.0.0"

__all__ = [
    # Core classes
    "SkillEvolutionTracker",
    "EvolutionGenerator",
    "EvolutionManager",
    # Models
    "EvolutionMode",
    "EvolutionProposal",
    "SkillMetrics",
    "EvolutionConfig",
    "ProposalStatus",
    # Exceptions
    "EvolutionError",
    "GenerationError",
    "ProposalError",
    "InvalidEvolutionModeError",
]
