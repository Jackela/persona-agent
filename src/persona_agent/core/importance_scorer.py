"""LLM-based importance scoring for memories.

Uses LLM to evaluate the importance of memories for long-term retention,
enabling smarter memory compression and retrieval prioritization.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class ImportanceLevel(Enum):
    """Importance levels for memories."""

    CRITICAL = 5  # Core user identity, major life events, permanent facts
    HIGH = 4  # Important preferences, significant events, strong emotions
    MEDIUM = 3  # Useful context, minor preferences, routine interactions
    LOW = 2  # Casual conversation, transient topics
    TRIVIAL = 1  # Greetings, filler, one-off questions


@dataclass
class ImportanceScore:
    """Importance score with reasoning."""

    score: int  # 1-5
    level: ImportanceLevel
    reasoning: str
    category: str  # e.g., "preference", "fact", "event", "identity"
    confidence: float  # 0.0-1.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImportanceScore:
        """Create from dict output."""
        score = data.get("score", 3)
        return cls(
            score=score,
            level=ImportanceLevel(score),
            reasoning=data.get("reasoning", ""),
            category=data.get("category", "unknown"),
            confidence=data.get("confidence", 0.5),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "score": self.score,
            "level": self.level.name,
            "reasoning": self.reasoning,
            "category": self.category,
            "confidence": self.confidence,
        }


class LLMClient(Protocol):
    """Protocol for LLM client."""

    async def chat(self, messages: list[dict[str, str]]) -> Any:
        """Send chat request."""
        ...


class ImportanceScorer:
    """LLM-based importance scorer for memories.

    Evaluates memories based on:
    - User identity and core facts
    - Long-term preferences and goals
    - Emotional significance
    - Information usefulness
    - Uniqueness and novelty
    """

    SCORING_PROMPT = """You are an AI memory importance evaluator. Your task is to score the importance of a conversation exchange for long-term memory retention.

Rate the importance from 1-5 based on these criteria:

5 - CRITICAL: Core user identity, major life events, permanent facts ("I am a doctor", "My name is Sarah", "I have two children")
4 - HIGH: Important preferences, significant events, strong emotions ("I hate mushrooms", "I got promoted", "I'm really anxious about exams")
3 - MEDIUM: Useful context, minor preferences, routine interactions ("I prefer tea over coffee", "I work remotely", "I'm learning Spanish")
2 - LOW: Casual conversation, transient topics ("The weather is nice", "I watched that movie", general chitchat)
1 - TRIVIAL: Greetings, filler, one-off questions ("Hello", "How are you?", "Thanks")

Consider:
- Would this information be useful in a future conversation?
- Does it reveal something important about the user's identity or preferences?
- Is it a long-term fact or temporary state?
- Would the user expect me to remember this?

Respond with a JSON object:
{
    "score": <1-5>,
    "reasoning": "<brief explanation>",
    "category": "<preference|fact|event|identity|emotion|other>",
    "confidence": <0.0-1.0>
}

Conversation to evaluate:
User: {user_message}
Assistant: {assistant_message}
"""

    def __init__(self, llm_client: LLMClient | None = None):
        """Initialize importance scorer.

        Args:
            llm_client: LLM client for scoring. If None, uses heuristic scoring.
        """
        self.llm_client = llm_client

    async def score_memory(
        self,
        user_message: str,
        assistant_message: str,
        context: dict[str, Any] | None = None,
    ) -> ImportanceScore:
        """Score a memory's importance.

        Args:
            user_message: User's message
            assistant_message: Assistant's response
            context: Optional context (previous memories, user model, etc.)

        Returns:
            Importance score with reasoning
        """
        if self.llm_client:
            try:
                return await self._llm_score(user_message, assistant_message)
            except Exception as e:
                logger.warning(f"LLM scoring failed, falling back to heuristic: {e}")

        return self._heuristic_score(user_message, assistant_message, context)

    async def _llm_score(
        self,
        user_message: str,
        assistant_message: str,
    ) -> ImportanceScore:
        """Use LLM to score importance."""
        prompt = self.SCORING_PROMPT.format(
            user_message=user_message[:500],
            assistant_message=assistant_message[:500],
        )

        messages = [
            {"role": "system", "content": "You are a helpful AI that evaluates memory importance."},
            {"role": "user", "content": prompt},
        ]

        assert self.llm_client is not None
        response = await self.llm_client.chat(messages)
        content = response.content if hasattr(response, "content") else str(response)

        # Parse JSON response
        try:
            # Extract JSON from response (may be wrapped in markdown)
            json_str = content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]

            data = json.loads(json_str.strip())
            return ImportanceScore.from_dict(data)
        except (json.JSONDecodeError, IndexError) as e:
            logger.warning(f"Failed to parse LLM scoring response: {e}")
            return ImportanceScore(
                score=3,
                level=ImportanceLevel.MEDIUM,
                reasoning="Failed to parse LLM response, using default",
                category="unknown",
                confidence=0.0,
            )

    def _heuristic_score(
        self,
        user_message: str,
        assistant_message: str,
        context: dict[str, Any] | None = None,
    ) -> ImportanceScore:
        """Fallback heuristic scoring based on keyword patterns."""
        text = f"{user_message} {assistant_message}".lower()

        # Identity indicators (high importance)
        identity_patterns = [
            "my name is",
            "i am a",
            "i work as",
            "i'm a",
            "i live in",
            "i have",
            "my job is",
            "i'm married",
            "i have kids",
        ]
        for pattern in identity_patterns:
            if pattern in text:
                return ImportanceScore(
                    score=5,
                    level=ImportanceLevel.CRITICAL,
                    reasoning=f"Contains identity indicator: '{pattern}'",
                    category="identity",
                    confidence=0.7,
                )

        # Preference indicators (medium-high importance)
        preference_patterns = [
            "i like",
            "i love",
            "i hate",
            "i prefer",
            "i enjoy",
            "i don't like",
            "i dislike",
            "my favorite",
        ]
        for pattern in preference_patterns:
            if pattern in text:
                return ImportanceScore(
                    score=4,
                    level=ImportanceLevel.HIGH,
                    reasoning=f"Contains preference indicator: '{pattern}'",
                    category="preference",
                    confidence=0.6,
                )

        # Emotional indicators
        emotion_patterns = [
            "i feel",
            "i'm happy",
            "i'm sad",
            "i'm angry",
            "i'm excited",
            "i'm worried",
            "i'm stressed",
            "i'm anxious",
        ]
        for pattern in emotion_patterns:
            if pattern in text:
                return ImportanceScore(
                    score=4,
                    level=ImportanceLevel.HIGH,
                    reasoning=f"Contains emotional indicator: '{pattern}'",
                    category="emotion",
                    confidence=0.6,
                )

        # Goal/plan indicators
        goal_patterns = [
            "i want to",
            "i plan to",
            "my goal is",
            "i'm trying to",
            "i hope to",
            "i'm working on",
        ]
        for pattern in goal_patterns:
            if pattern in text:
                return ImportanceScore(
                    score=4,
                    level=ImportanceLevel.HIGH,
                    reasoning=f"Contains goal indicator: '{pattern}'",
                    category="goal",
                    confidence=0.6,
                )

        # Question indicators (usually lower importance)
        if "?" in user_message and len(user_message) < 50:
            return ImportanceScore(
                score=1,
                level=ImportanceLevel.TRIVIAL,
                reasoning="Short question",
                category="question",
                confidence=0.5,
            )

        # Greeting indicators
        greeting_patterns = ["hello", "hi", "hey", "good morning", "good evening"]
        if any(g in text[:20] for g in greeting_patterns) and len(text) < 30:
            return ImportanceScore(
                score=1,
                level=ImportanceLevel.TRIVIAL,
                reasoning="Greeting",
                category="greeting",
                confidence=0.7,
            )

        # Default: medium importance
        return ImportanceScore(
            score=3,
            level=ImportanceLevel.MEDIUM,
            reasoning="No strong indicators, default score",
            category="general",
            confidence=0.4,
        )

    def should_retain(
        self,
        score: ImportanceScore,
        threshold: ImportanceLevel = ImportanceLevel.LOW,
    ) -> bool:
        """Check if a memory should be retained based on its score.

        Args:
            score: Importance score
            threshold: Minimum importance level to retain

        Returns:
            True if memory should be retained
        """
        return score.score >= threshold.value

    def get_compression_priority(
        self,
        score: ImportanceScore,
    ) -> int:
        """Get compression priority (lower = compress later).

        Args:
            score: Importance score

        Returns:
            Priority value (1 = most important, 5 = least important)
        """
        return 6 - score.score  # Invert so 5 -> 1, 1 -> 5
