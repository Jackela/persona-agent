"""Memory summarizer for generating summaries of memory groups."""

from __future__ import annotations

from typing import Any


class MemorySummarizer:
    """Summarizes groups of memories into concise summaries."""

    def __init__(self, llm_client: Any | None = None) -> None:
        """Initialize summarizer.

        Args:
            llm_client: Optional LLM client for generating summaries
        """
        self.llm_client = llm_client

    async def summarize_memories(
        self,
        memories: list[dict[str, Any]],
        max_length: int = 500,
    ) -> str:
        """Summarize a group of memories.

        Args:
            memories: List of memory entries with content
            max_length: Maximum length of summary

        Returns:
            Generated summary string
        """
        if not memories:
            return ""

        if self.llm_client is None:
            # Fallback: simple concatenation
            contents = [m.get("content", "")[:200] for m in memories]
            summary = " | ".join(contents)
            return summary[:max_length]

        # Use LLM to generate summary
        memory_texts = []
        for i, mem in enumerate(memories, 1):
            content = mem.get("content", "")
            memory_texts.append(f"{i}. {content}")

        prompt = f"""Summarize the following conversation memories into a concise summary.

Memories:
{"\n".join(memory_texts)}

Provide a brief summary (max {max_length} chars) capturing the key points and themes."""

        response = await self.llm_client.chat([{"role": "user", "content": prompt}])
        return response.content[:max_length]
