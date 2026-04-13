"""Advanced memory compression with LLM-based summarization.

Provides intelligent compression of conversation history by:
- LLM-based summarization of important exchanges
- Multi-level memory hierarchy (raw -> summary -> archive)
- Importance-weighted compression decisions
- Preservation of key facts and user preferences
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from persona_agent.core.importance_scorer import ImportanceScore

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    """Protocol for LLM client."""

    async def chat(self, messages: list[dict[str, str]]) -> Any:
        """Send chat request."""
        ...


@dataclass
class CompressedMemory:
    """A compressed memory entry."""

    original_ids: list[str]  # IDs of original memories
    summary: str  # LLM-generated summary
    key_facts: list[str]  # Extracted key facts
    importance_range: tuple[int, int]  # (min, max) importance scores
    timestamp_range: tuple[float, float]  # (start, end) timestamps
    compression_ratio: float  # Original chars / compressed chars
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "original_ids": self.original_ids,
            "summary": self.summary,
            "key_facts": self.key_facts,
            "importance_range": self.importance_range,
            "timestamp_range": self.timestamp_range,
            "compression_ratio": self.compression_ratio,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompressedMemory:
        """Create from dict."""
        return cls(
            original_ids=data["original_ids"],
            summary=data["summary"],
            key_facts=data["key_facts"],
            importance_range=tuple(data["importance_range"]),
            timestamp_range=tuple(data["timestamp_range"]),
            compression_ratio=data["compression_ratio"],
            metadata=data.get("metadata", {}),
        )


class MemoryCompressor:
    """LLM-based memory compression system.

    Compresses groups of memories into summaries while preserving
    important information based on importance scores.
    """

    COMPRESSION_PROMPT = """Summarize the following conversation exchanges concisely while preserving important information.

Important information includes:
- User identity, personal facts, relationships
- Preferences, likes/dislikes
- Goals, plans, aspirations
- Significant events or experiences
- Strong emotions or reactions

Conversation exchanges:
{exchanges}

Provide your summary in this JSON format:
{{
    "summary": "<concise narrative summary of the conversation>",
    "key_facts": [
        "<key fact 1>",
        "<key fact 2>",
        ...
    ],
    "topics": ["<topic 1>", "<topic 2>", ...]
}}

Keep the summary under 200 words. Extract 3-7 key facts."""

    def __init__(self, llm_client: LLMClient | None = None):
        """Initialize memory compressor.

        Args:
            llm_client: LLM client for compression
        """
        self.llm_client = llm_client

    async def compress_memories(
        self,
        memories: list[dict[str, Any]],
        importance_scores: list[ImportanceScore] | None = None,
    ) -> CompressedMemory | None:
        """Compress a group of memories into a summary.

        Args:
            memories: List of memory dicts with user_message, assistant_message
            importance_scores: Optional importance scores for each memory

        Returns:
            Compressed memory or None if compression failed
        """
        if len(memories) < 2:
            return None  # Don't compress single memories

        if not self.llm_client:
            return self._heuristic_compress(memories, importance_scores)

        try:
            return await self._llm_compress(memories, importance_scores)
        except Exception as e:
            logger.warning(f"LLM compression failed, using heuristic: {e}")
            return self._heuristic_compress(memories, importance_scores)

    async def _llm_compress(
        self,
        memories: list[dict[str, Any]],
        importance_scores: list[ImportanceScore] | None = None,
    ) -> CompressedMemory:
        """Use LLM to compress memories."""
        # Format exchanges
        exchanges = []
        for i, mem in enumerate(memories, 1):
            score_info = ""
            if importance_scores and i <= len(importance_scores):
                score = importance_scores[i - 1]
                score_info = f" [Importance: {score.level.name}]"

            exchanges.append(
                f"Exchange {i}{score_info}:\n"
                f"User: {mem.get('user_message', '')}\n"
                f"Assistant: {mem.get('assistant_message', '')}"
            )

        exchanges_text = "\n\n".join(exchanges)

        messages = [
            {
                "role": "system",
                "content": "You are a helpful AI that summarizes conversations accurately.",
            },
            {"role": "user", "content": self.COMPRESSION_PROMPT.format(exchanges=exchanges_text)},
        ]

        response = await self.llm_client.chat(messages)
        content = response.content if hasattr(response, "content") else str(response)

        # Parse JSON response
        try:
            json_str = content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]

            data = json.loads(json_str.strip())

            # Calculate compression ratio
            original_chars = sum(
                len(m.get("user_message", "")) + len(m.get("assistant_message", ""))
                for m in memories
            )
            compressed_chars = len(data.get("summary", ""))
            ratio = original_chars / max(compressed_chars, 1)

            # Extract importance range
            if importance_scores:
                scores = [s.score for s in importance_scores]
                imp_range = (min(scores), max(scores))
            else:
                imp_range = (3, 3)

            # Extract timestamps
            timestamps = [
                m.get("timestamp", 0) for m in memories if "timestamp" in m
            ]
            time_range = (min(timestamps), max(timestamps)) if timestamps else (0, 0)

            return CompressedMemory(
                original_ids=[str(m.get("id", "")) for m in memories],
                summary=data.get("summary", ""),
                key_facts=data.get("key_facts", []),
                importance_range=imp_range,
                timestamp_range=time_range,
                compression_ratio=ratio,
                metadata={"topics": data.get("topics", [])},
            )

        except (json.JSONDecodeError, IndexError) as e:
            logger.error(f"Failed to parse compression response: {e}")
            return self._heuristic_compress(memories, importance_scores)

    def _heuristic_compress(
        self,
        memories: list[dict[str, Any]],
        importance_scores: list[ImportanceScore] | None = None,
    ) -> CompressedMemory:
        """Fallback heuristic compression."""
        # Keep only high-importance exchanges
        important_exchanges = []
        for i, mem in enumerate(memories):
            keep = True
            if importance_scores and i < len(importance_scores):
                if importance_scores[i].score < 3:
                    keep = False

            if keep:
                important_exchanges.append(
                    f"User: {mem.get('user_message', '')}\n"
                    f"Assistant: {mem.get('assistant_message', '')}"
                )

        summary = "\n\n".join(important_exchanges) if important_exchanges else "[Conversation history]"

        # Extract key facts from high-importance memories
        key_facts = []
        if importance_scores:
            for i, score in enumerate(importance_scores):
                if score.score >= 4 and i < len(memories):
                    mem = memories[i]
                    fact = f"{mem.get('user_message', '')} -> {mem.get('assistant_message', '')}"
                    key_facts.append(fact[:200])

        # Calculate ranges
        if importance_scores:
            scores = [s.score for s in importance_scores]
            imp_range = (min(scores), max(scores))
        else:
            imp_range = (3, 3)

        timestamps = [
            m.get("timestamp", 0) for m in memories if "timestamp" in m
        ]
        time_range = (min(timestamps), max(timestamps)) if timestamps else (0, 0)

        original_chars = sum(
            len(m.get("user_message", "")) + len(m.get("assistant_message", ""))
            for m in memories
        )
        compressed_chars = len(summary)
        ratio = original_chars / max(compressed_chars, 1)

        return CompressedMemory(
            original_ids=[str(m.get("id", "")) for m in memories],
            summary=summary[:500],
            key_facts=key_facts[:5],
            importance_range=imp_range,
            timestamp_range=time_range,
            compression_ratio=ratio,
            metadata={"method": "heuristic"},
        )

    def select_memories_for_compression(
        self,
        memories: list[dict[str, Any]],
        importance_scores: list[ImportanceScore],
        target_count: int = 10,
    ) -> list[list[dict[str, Any]]]:
        """Select groups of memories for compression.

        Selects lower-importance memories for compression while
        preserving high-importance ones.

        Args:
            memories: List of memories
            importance_scores: Corresponding importance scores
            target_count: Target number of memories to keep uncompressed

        Returns:
            List of memory groups to compress
        """
        if len(memories) <= target_count:
            return []

        # Sort by importance score (ascending - least important first)
        indexed = list(enumerate(zip(memories, importance_scores, strict=False)))
        indexed.sort(key=lambda x: x[1][1].score)

        # Select memories to compress (lower importance first)
        to_compress_count = len(memories) - target_count
        to_compress_indices = [idx for idx, _ in indexed[:to_compress_count]]
        to_compress_indices.sort()  # Restore original order

        # Group consecutive memories for better compression
        groups = []
        current_group = []

        for idx in to_compress_indices:
            if not current_group or idx == current_group[-1] + 1:
                current_group.append(idx)
            else:
                # Start new group
                groups.append([memories[i] for i in current_group])
                current_group = [idx]

        if current_group:
            groups.append([memories[i] for i in current_group])

        return groups
