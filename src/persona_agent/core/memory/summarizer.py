"""Memory summarization using LLM.

This module provides LLM-based summarization of memory groups,
extracting key information and themes from multiple memories.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from persona_agent.core.memory.exceptions import SummarizationError

if TYPE_CHECKING:
    from persona_agent.core.hierarchical_memory import EpisodicEntry
    from persona_agent.utils.llm_client import LLMResponse

logger = logging.getLogger(__name__)


class LLMClientProtocol(Protocol):
    """Protocol for LLM client interactions."""

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
    ) -> LLMResponse: ...


@dataclass
class SummaryMetadata:
    """Metadata about a generated summary."""

    original_count: int
    source_date_range: tuple[str, str] | None = None
    key_entities: list[str] = None
    key_themes: list[str] = None
    confidence: float = 0.0

    def __post_init__(self):
        if self.key_entities is None:
            self.key_entities = []
        if self.key_themes is None:
            self.key_themes = []


class MemorySummarizer:
    """Summarize groups of memories using LLM.

    This class takes a collection of episodic memories and generates
    a concise summary capturing the key information and themes.

    Example:
        summarizer = MemorySummarizer(llm_client)
        summary = await summarizer.summarize(memories)
    """

    SUMMARIZATION_PROMPT_TEMPLATE = """You are a memory summarization assistant. Your task is to create a concise summary of the following conversation memories.

Memories from {date_range}:
{memories_text}

Instructions:
1. Create a coherent summary that captures the key events, information, and themes
2. Preserve important facts, decisions, and user preferences
3. Maintain temporal sequence where relevant
4. Include relevant entity names and specific details
5. Keep the summary concise but comprehensive

Provide your response as JSON:
{{
  "summary": "Your summary text here (max {max_length} chars)",
  "key_entities": ["entity1", "entity2"],
  "key_themes": ["theme1", "theme2"],
  "confidence": 0.85
}}

The summary should be written in third person and focus on factual content."""

    def __init__(
        self,
        llm_client: LLMClientProtocol | None = None,
        max_summary_length: int = 500,
    ) -> None:
        """Initialize the summarizer.

        Args:
            llm_client: LLM client for generating summaries
            max_summary_length: Maximum length of generated summaries
        """
        self.llm_client = llm_client
        self.max_summary_length = max_summary_length

    async def summarize(
        self,
        memories: list[EpisodicEntry],
    ) -> tuple[str, SummaryMetadata]:
        """Generate a summary of the provided memories.

        Args:
            memories: List of episodic memory entries to summarize

        Returns:
            Tuple of (summary_text, metadata)

        Raises:
            SummarizationError: If summarization fails
        """
        if not memories:
            raise SummarizationError("Cannot summarize empty memory list")

        if not self.llm_client:
            # Fallback to simple concatenation
            return self._fallback_summarize(memories)

        try:
            prompt = self._build_prompt(memories)

            response = await self.llm_client.chat(
                messages=[
                    {"role": "system", "content": "You are a precise memory summarization assistant."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )

            return self._parse_response(response.content, memories)

        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            raise SummarizationError(
                f"Failed to summarize {len(memories)} memories: {e}",
                memory_count=len(memories),
                prompt_length=len(prompt) if 'prompt' in locals() else 0,
            )

    def _build_prompt(self, memories: list[EpisodicEntry]) -> str:
        """Build the summarization prompt."""
        from datetime import datetime

        # Sort memories by timestamp
        sorted_memories = sorted(memories, key=lambda m: m.timestamp)

        # Build date range
        if len(sorted_memories) >= 2:
            start_date = sorted_memories[0].timestamp.strftime("%Y-%m-%d")
            end_date = sorted_memories[-1].timestamp.strftime("%Y-%m-%d")
            date_range = f"{start_date} to {end_date}" if start_date != end_date else start_date
        else:
            date_range = sorted_memories[0].timestamp.strftime("%Y-%m-%d")

        # Build memories text
        memory_lines = []
        for i, memory in enumerate(sorted_memories, 1):
            timestamp_str = memory.timestamp.strftime("%H:%M")
            content = memory.content[:200]  # Truncate long memories
            memory_lines.append(f"{i}. [{timestamp_str}] {content}")

        memories_text = "\n".join(memory_lines)

        return self.SUMMARIZATION_PROMPT_TEMPLATE.format(
            date_range=date_range,
            memories_text=memories_text,
            max_length=self.max_summary_length,
        )

    def _parse_response(
        self,
        content: str,
        memories: list[EpisodicEntry],
    ) -> tuple[str, SummaryMetadata]:
        """Parse the LLM response into summary and metadata."""
        try:
            # Extract JSON from markdown if present
            json_content = self._extract_json(content)
            data = json.loads(json_content)

            summary = data.get("summary", "")
            if len(summary) > self.max_summary_length:
                summary = summary[: self.max_summary_length - 3] + "..."

            # Build metadata
            sorted_memories = sorted(memories, key=lambda m: m.timestamp)
            metadata = SummaryMetadata(
                original_count=len(memories),
                source_date_range=(
                    sorted_memories[0].timestamp.isoformat(),
                    sorted_memories[-1].timestamp.isoformat(),
                )
                if len(sorted_memories) >= 2
                else None,
                key_entities=data.get("key_entities", []),
                key_themes=data.get("key_themes", []),
                confidence=data.get("confidence", 0.5),
            )

            return summary, metadata

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            # Use raw content as summary
            summary = content[: self.max_summary_length]
            metadata = SummaryMetadata(
                original_count=len(memories),
                confidence=0.3,
            )
            return summary, metadata

    def _extract_json(self, content: str) -> str:
        """Extract JSON from content that may be wrapped in markdown."""
        import re

        # Try code blocks first
        for pattern in [r"```json\s*(.*?)\s*```", r"```\s*(.*?)\s*```"]:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                return match.group(1).strip()

        # Try to find JSON object directly
        match = re.search(r"(\{[\s\S]*\})", content)
        if match:
            return match.group(1).strip()

        return content.strip()

    def _fallback_summarize(
        self,
        memories: list[EpisodicEntry],
    ) -> tuple[str, SummaryMetadata]:
        """Fallback summarization without LLM."""
        sorted_memories = sorted(memories, key=lambda m: m.timestamp)

        # Simple concatenation with truncation
        contents = [m.content[:150] for m in sorted_memories]
        summary = " | ".join(contents)

        if len(summary) > self.max_summary_length:
            summary = summary[: self.max_summary_length - 3] + "..."

        # Extract unique entities from all memories
        all_entities: set[str] = set()
        for memory in memories:
            all_entities.update(memory.entities)

        metadata = SummaryMetadata(
            original_count=len(memories),
            source_date_range=(
                sorted_memories[0].timestamp.isoformat(),
                sorted_memories[-1].timestamp.isoformat(),
            )
            if len(sorted_memories) >= 2
            else None,
            key_entities=list(all_entities)[:10],
            confidence=0.5,
        )

        return summary, metadata


__all__ = [
    "MemorySummarizer",
    "SummaryMetadata",
    "LLMClientProtocol",
]
