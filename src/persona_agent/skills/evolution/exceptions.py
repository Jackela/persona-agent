"""Exceptions for the skill evolution system."""

from __future__ import annotations


class EvolutionError(Exception):
    """Base exception for skill evolution errors."""

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class TrackingError(EvolutionError):
    """Raised when skill tracking fails."""

    pass


class GenerationError(EvolutionError):
    """Raised when evolution generation fails.

    This typically indicates:
    - LLM service unavailable
    - Invalid skill code
    - Response parsing errors
    """

    def __init__(
        self,
        message: str,
        *,
        skill_name: str | None = None,
        mode: str | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.skill_name = skill_name
        self.mode = mode


class ProposalError(EvolutionError):
    """Raised when proposal management fails."""

    def __init__(
        self,
        message: str,
        *,
        proposal_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.proposal_id = proposal_id


class InvalidEvolutionModeError(EvolutionError):
    """Raised when an invalid evolution mode is specified."""

    def __init__(self, mode: str) -> None:
        super().__init__(f"Invalid evolution mode: {mode}")
        self.mode = mode


class ValidationError(EvolutionError):
    """Raised when evolved skill validation fails."""

    def __init__(
        self,
        message: str,
        *,
        errors: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.errors = errors or []


__all__ = [
    "EvolutionError",
    "TrackingError",
    "GenerationError",
    "ProposalError",
    "InvalidEvolutionModeError",
    "ValidationError",
]
