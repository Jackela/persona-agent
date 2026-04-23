"""Evolution manager for handling proposal lifecycle.

This module provides the EvolutionManager class for managing
the complete lifecycle of evolution proposals from creation
to approval/rejection.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from persona_agent.skills.evolution.exceptions import ProposalError, ValidationError
from persona_agent.skills.evolution.models import (
    EvolutionConfig,
    EvolutionMode,
    EvolutionProposal,
    ProposalStatus,
)
from persona_agent.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


class EvolutionManager:
    """Manage the lifecycle of evolution proposals.

    This class handles:
    - Storing and retrieving proposals
    - Approval workflow
    - Activation of approved skills
    - Cleanup of old proposals

    Example:
        manager = EvolutionManager(config)
        await manager.store_proposal(proposal)

        # Later, after review
        await manager.approve_proposal(proposal.id, reviewer="admin")
    """

    def __init__(self, config: EvolutionConfig | None = None) -> None:
        """Initialize the manager.

        Args:
            config: Evolution configuration
        """
        self.config = config or EvolutionConfig()
        self._proposals: dict[str, EvolutionProposal] = {}
        self._storage_path = Path(self.config.storage_path)

        # Ensure storage directory exists
        self._setup_storage()

    def _setup_storage(self) -> None:
        """Setup storage directories."""
        directories = [
            self._storage_path / "pending",
            self._storage_path / "approved",
            self._storage_path / "rejected",
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    async def store_proposal(self, proposal: EvolutionProposal) -> None:
        """Store a new proposal.

        Args:
            proposal: The proposal to store

        Raises:
            ProposalError: If proposal cannot be stored
        """
        # Check pending limit
        _ = len(self._get_proposals_by_status(ProposalStatus.PENDING))  # For monitoring
        skill_pending = sum(
            1
            for p in self._proposals.values()
            if p.skill_name == proposal.skill_name and p.is_pending
        )

        if skill_pending >= self.config.max_proposals_per_skill:
            raise ProposalError(
                f"Maximum pending proposals reached for {proposal.skill_name}",
                proposal_id=proposal.id,
            )

        # Store in memory
        self._proposals[proposal.id] = proposal

        # Store on disk
        await self._save_proposal(proposal)

        logger.info(f"Stored proposal {proposal.id} for {proposal.skill_name}")

    async def get_proposal(self, proposal_id: str) -> EvolutionProposal | None:
        """Get a proposal by ID.

        Args:
            proposal_id: The proposal ID

        Returns:
            The proposal or None if not found
        """
        # Check memory first
        if proposal_id in self._proposals:
            return self._proposals[proposal_id]

        # Try to load from disk
        return await self._load_proposal(proposal_id)

    async def list_proposals(
        self,
        status: ProposalStatus | None = None,
        skill_name: str | None = None,
    ) -> list[EvolutionProposal]:
        """List proposals with optional filtering.

        Args:
            status: Filter by status
            skill_name: Filter by skill name

        Returns:
            List of matching proposals
        """
        proposals = list(self._proposals.values())

        if status:
            proposals = [p for p in proposals if p.status == status]

        if skill_name:
            proposals = [p for p in proposals if p.skill_name == skill_name]

        # Sort by creation time (newest first)
        proposals.sort(key=lambda p: p.created_at, reverse=True)

        return proposals

    async def approve_proposal(
        self,
        proposal_id: str,
        reviewer: str,
        skill_registry: SkillRegistry | None = None,
    ) -> bool:
        """Approve and activate a proposal.

        Args:
            proposal_id: The proposal to approve
            reviewer: Name of the reviewer
            skill_registry: Optional registry to register the new skill

        Returns:
            True if approved successfully

        Raises:
            ProposalError: If approval fails
        """
        proposal = await self.get_proposal(proposal_id)
        if not proposal:
            raise ProposalError(f"Proposal not found: {proposal_id}", proposal_id=proposal_id)

        if not proposal.is_pending:
            raise ProposalError(
                f"Proposal is not pending: {proposal.status.value}",
                proposal_id=proposal_id,
            )

        # Validate the proposed code
        if not self._validate_code(proposal.proposed_code):
            raise ValidationError("Proposed code failed validation")

        # Approve
        proposal.approve(reviewer)

        # Move to approved directory
        await self._move_proposal(proposal, ProposalStatus.APPROVED)

        # Optionally register with skill registry
        if skill_registry:
            # This would require dynamic class loading
            logger.info(f"Would register evolved skill {proposal.skill_name}")

        logger.info(f"Approved proposal {proposal_id} by {reviewer}")
        return True

    async def reject_proposal(
        self,
        proposal_id: str,
        reason: str,
        reviewer: str,
    ) -> bool:
        """Reject a proposal.

        Args:
            proposal_id: The proposal to reject
            reason: Reason for rejection
            reviewer: Name of the reviewer

        Returns:
            True if rejected successfully
        """
        proposal = await self.get_proposal(proposal_id)
        if not proposal:
            raise ProposalError(f"Proposal not found: {proposal_id}", proposal_id=proposal_id)

        proposal.reject(reason, reviewer)
        await self._move_proposal(proposal, ProposalStatus.REJECTED)

        logger.info(f"Rejected proposal {proposal_id} by {reviewer}: {reason}")
        return True

    async def cleanup_expired_proposals(self) -> int:
        """Clean up expired pending proposals.

        Returns:
            Number of proposals expired
        """
        expired = []
        cutoff = datetime.now(UTC) - timedelta(hours=self.config.proposal_expiry_hours)

        for proposal in self._proposals.values():
            if proposal.is_pending and proposal.created_at < cutoff:
                expired.append(proposal)

        for proposal in expired:
            proposal.status = ProposalStatus.EXPIRED
            await self._move_proposal(proposal, ProposalStatus.EXPIRED)
            logger.info(f"Expired proposal {proposal.id}")

        return len(expired)

    async def _save_proposal(self, proposal: EvolutionProposal) -> None:
        """Save proposal to disk."""
        directory = self._storage_path / proposal.status.value
        file_path = directory / f"{proposal.id}.json"

        data = {
            "id": proposal.id,
            "skill_name": proposal.skill_name,
            "mode": proposal.mode.value,
            "original_code": proposal.original_code,
            "proposed_code": proposal.proposed_code,
            "reasoning": proposal.reasoning,
            "created_at": proposal.created_at.isoformat(),
            "status": proposal.status.value,
            "reviewed_at": proposal.reviewed_at.isoformat() if proposal.reviewed_at else None,
            "reviewed_by": proposal.reviewed_by,
            "rejection_reason": proposal.rejection_reason,
            "metrics_at_creation": proposal.metrics_at_creation,
            "parent_proposal_id": proposal.parent_proposal_id,
        }

        file_path.write_text(json.dumps(data, indent=2))

    async def _load_proposal(self, proposal_id: str) -> EvolutionProposal | None:
        """Load proposal from disk."""
        for status in ProposalStatus:
            file_path = self._storage_path / status.value / f"{proposal_id}.json"
            if file_path.exists():
                data = json.loads(file_path.read_text())
                proposal = EvolutionProposal(
                    id=data["id"],
                    skill_name=data["skill_name"],
                    mode=EvolutionMode(data["mode"]),
                    original_code=data["original_code"],
                    proposed_code=data["proposed_code"],
                    reasoning=data["reasoning"],
                    created_at=datetime.fromisoformat(data["created_at"]),
                    status=ProposalStatus(data["status"]),
                    reviewed_at=(
                        datetime.fromisoformat(data["reviewed_at"])
                        if data.get("reviewed_at")
                        else None
                    ),
                    reviewed_by=data.get("reviewed_by"),
                    rejection_reason=data.get("rejection_reason"),
                    metrics_at_creation=data.get("metrics_at_creation", {}),
                    parent_proposal_id=data.get("parent_proposal_id"),
                )
                self._proposals[proposal_id] = proposal
                return proposal

        return None

    async def _move_proposal(
        self,
        proposal: EvolutionProposal,
        new_status: ProposalStatus,
    ) -> None:
        """Move proposal file to new status directory."""
        old_dir = self._storage_path / proposal.status.value
        new_dir = self._storage_path / new_status.value

        old_path = old_dir / f"{proposal.id}.json"
        new_path = new_dir / f"{proposal.id}.json"

        if old_path.exists():
            shutil.move(str(old_path), str(new_path))

        await self._save_proposal(proposal)

    def _get_proposals_by_status(self, status: ProposalStatus) -> list[EvolutionProposal]:
        """Get all proposals with given status."""
        return [p for p in self._proposals.values() if p.status == status]

    def _validate_code(self, code: str) -> bool:
        """Validate that code is syntactically correct Python."""
        try:
            compile(code, "<string>", "exec")
            return True
        except SyntaxError as e:
            logger.error(f"Code validation failed: {e}")
            return False

    def get_statistics(self) -> dict[str, Any]:
        """Get manager statistics."""
        return {
            "total_proposals": len(self._proposals),
            "pending": len(self._get_proposals_by_status(ProposalStatus.PENDING)),
            "approved": len(self._get_proposals_by_status(ProposalStatus.APPROVED)),
            "rejected": len(self._get_proposals_by_status(ProposalStatus.REJECTED)),
            "storage_path": str(self._storage_path),
        }


__all__ = ["EvolutionManager"]
