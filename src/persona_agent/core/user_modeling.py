"""Adaptive User Modeling System for Persona-Agent.

Inspired by Honcho (https://github.com/plastic-labs/honcho) - treats memory as
reasoning, not storage. Implements the "peer paradigm" where both users and
agents are "peers" with directional learning.

Key concepts:
- Treat memory as reasoning, not storage
- Peer paradigm: both users and agents are "peers"
- Formal logic reasoning: deductive, inductive, abductive conclusions
- Peer Card: up to 40 biographical facts for quick reference
- Conclusions: reasoned insights with premises
- Directional learning: different peers have different views of each other
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from collections import deque
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    from persona_agent.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


# ============================================================================
# Conclusion System - Formal Logic Reasoning
# ============================================================================


class Conclusion(BaseModel):
    """A reasoned conclusion about the user.

    Conclusions are not just stored facts - they are reasoned insights
    derived through formal logic:
    - Deductive: logical inferences from premises (general to specific)
    - Inductive: pattern recognition from observations (specific to general)
    - Abductive: best explanations for observations (inference to best explanation)
    """

    conclusion_type: Literal["deductive", "inductive", "abductive"]
    premises: list[str] = Field(default_factory=list)
    conclusion: str
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.now)
    source_interaction: str = ""  # Reference to originating interaction

    def to_prompt_context(self) -> str:
        """Format conclusion for inclusion in prompts."""
        return f"[{self.conclusion_type.upper()}] {self.conclusion} (confidence: {self.confidence:.2f})"


# ============================================================================
# Peer Card - Quick Reference Biographical Cache
# ============================================================================


class UserPeerCard(BaseModel):
    """Quick-reference biographical cache (max 40 facts).

    The Peer Card serves as a rapidly accessible cache of the most
    important biographical information about the user. Facts are
    maintained with LRU eviction when max size is reached.
    """

    facts: list[str] = Field(default_factory=list)
    access_timestamps: list[datetime] = Field(default_factory=list)

    @field_validator("facts")
    @classmethod
    def validate_max_facts(cls, v: list[str]) -> list[str]:
        """Ensure facts list doesn't exceed max size."""
        if len(v) > 40:
            return v[-40:]
        return v

    def add_fact(self, fact: str) -> None:
        """Add a fact, maintaining max size with LRU eviction.

        If at max capacity (40 facts), removes the least recently
        accessed fact before adding the new one.
        """
        # Normalize fact text
        fact = fact.strip()
        if not fact:
            return

        # Check if fact already exists
        if fact in self.facts:
            # Move to end (most recently used)
            idx = self.facts.index(fact)
            self.facts.pop(idx)
            if idx < len(self.access_timestamps):
                self.access_timestamps.pop(idx)

        # Evict oldest if at capacity
        if len(self.facts) >= 40:
            self.facts.pop(0)
            if self.access_timestamps:
                self.access_timestamps.pop(0)

        # Add new fact
        self.facts.append(fact)
        self.access_timestamps.append(datetime.now())

    def access_fact(self, fact: str) -> bool:
        """Mark a fact as accessed (updates LRU timestamp).

        Returns True if fact was found and updated, False otherwise.
        """
        if fact not in self.facts:
            return False

        idx = self.facts.index(fact)
        if idx < len(self.access_timestamps):
            self.access_timestamps[idx] = datetime.now()
        return True

    def get_facts(self, category: str | None = None) -> list[str]:
        """Get facts, optionally filtered by category prefix."""
        if category is None:
            return self.facts.copy()

        prefix = f"[{category}]"
        return [f for f in self.facts if f.startswith(prefix)]

    def merge_facts(self, new_facts: list[str], source: str = "") -> None:
        """Merge multiple facts into the peer card."""
        for fact in new_facts:
            if source:
                fact = f"[{source}] {fact}"
            self.add_fact(fact)


# ============================================================================
# User Preference with Confidence Tracking
# ============================================================================


class UserPreference(BaseModel):
    """A learned user preference with confidence scoring.

    Preferences are learned over time with confidence scores that
    increase with supporting evidence and decrease with contradictory
    observations.
    """

    category: str  # "communication", "content", "topic", "style", etc.
    value: str
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    learned_from: str = ""  # Which interaction taught us this
    learned_at: datetime = Field(default_factory=datetime.now)
    evidence_count: int = 1
    last_reinforced_at: datetime = Field(default_factory=datetime.now)

    def reinforce(self, source: str = "") -> None:
        """Reinforce this preference with additional evidence.

        Increases confidence using a logarithmic scale to prevent
        over-confidence while still allowing learning.
        """
        self.evidence_count += 1
        self.last_reinforced_at = datetime.now()

        # Logarithmic confidence growth: approaches 1.0 but never reaches it
        # New confidence = 1 - (1 - old_confidence) * decay_factor
        decay_factor = 0.9  # Each new evidence reduces uncertainty by 10%
        self.confidence = 1.0 - (1.0 - self.confidence) * decay_factor

        if source:
            self.learned_from = source

    def contradict(self) -> None:
        """Record contradictory evidence.

        Decreases confidence when the preference is contradicted.
        """
        self.evidence_count = max(1, self.evidence_count - 1)
        # Reduce confidence more aggressively than we increase it
        self.confidence = max(0.1, self.confidence * 0.7)

    def to_prompt_context(self) -> str:
        """Format preference for inclusion in prompts."""
        return f"- {self.category}: {self.value} (confidence: {self.confidence:.0%})"


# ============================================================================
# Complete User Model
# ============================================================================


class UserModel(BaseModel):
    """Complete user model with preferences, patterns, and relationship dynamics.

    The UserModel implements the "peer paradigm" - treating the user
    as a peer with their own state, preferences, and relationship dynamics
    with the agent.
    """

    user_id: str
    peer_card: UserPeerCard = Field(default_factory=UserPeerCard)
    conclusions: list[Conclusion] = Field(default_factory=list)

    # Preferences with confidence scores (keyed by "category:value")
    preferences: dict[str, UserPreference] = Field(default_factory=dict)

    # Emotional triggers (topic -> intensity mapping)
    emotional_triggers: dict[str, float] = Field(default_factory=dict)

    # Relationship dynamics
    trust_level: float = Field(0.3, ge=0.0, le=1.0)
    familiarity: float = Field(0.0, ge=0.0, le=1.0)
    preferred_style: str = ""  # e.g., "formal", "casual", "humorous"

    # Temporal tracking
    interaction_count: int = 0
    total_messages: int = 0
    first_interaction_at: datetime = Field(default_factory=datetime.now)
    last_interaction_at: datetime | None = None

    # Interaction patterns (recent patterns for trend analysis)
    interaction_patterns: list[dict[str, Any]] = Field(default_factory=list)

    # Metadata
    version: str = "1.0.0"
    updated_at: datetime = Field(default_factory=datetime.now)

    def add_conclusion(self, conclusion: Conclusion) -> None:
        """Add a new conclusion to the user model."""
        self.conclusions.append(conclusion)
        self.updated_at = datetime.now()

        # Also add high-confidence conclusions to peer card
        if conclusion.confidence >= 0.7:
            self.peer_card.add_fact(f"[conclusion] {conclusion.conclusion}")

    def add_preference(self, preference: UserPreference) -> None:
        """Add or update a preference."""
        key = f"{preference.category}:{preference.value}"

        if key in self.preferences:
            # Reinforce existing preference
            self.preferences[key].reinforce(preference.learned_from)
        else:
            # Add new preference
            self.preferences[key] = preference

        self.updated_at = datetime.now()

    def get_preferences_by_category(self, category: str) -> list[UserPreference]:
        """Get all preferences in a specific category."""
        return [p for p in self.preferences.values() if p.category == category]

    def update_emotional_trigger(self, trigger: str, intensity: float) -> None:
        """Update emotional trigger intensity (exponential moving average)."""
        alpha = 0.3  # Smoothing factor
        current = self.emotional_triggers.get(trigger, 0.0)
        self.emotional_triggers[trigger] = (alpha * intensity) + ((1 - alpha) * current)
        self.updated_at = datetime.now()

    def record_interaction(self, pattern: dict[str, Any]) -> None:
        """Record an interaction pattern.

        Maintains a rolling window of recent patterns for trend analysis.
        """
        self.interaction_count += 1
        self.total_messages += 2  # User + assistant messages
        self.last_interaction_at = datetime.now()
        self.updated_at = datetime.now()

        # Add pattern with timestamp
        pattern["timestamp"] = datetime.now().isoformat()
        self.interaction_patterns.append(pattern)

        # Keep only recent patterns (last 100)
        if len(self.interaction_patterns) > 100:
            self.interaction_patterns = self.interaction_patterns[-100:]

    def get_recent_patterns(self, n: int = 10) -> list[dict[str, Any]]:
        """Get the n most recent interaction patterns."""
        return self.interaction_patterns[-n:]

    def to_dict(self) -> dict[str, Any]:
        """Serialize user model to dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserModel:
        """Deserialize user model from dictionary."""
        return cls.model_validate(data)


# ============================================================================
# Storage Interface
# ============================================================================


class UserModelStorage(ABC):
    """Abstract storage interface for user models."""

    @abstractmethod
    async def get(self, user_id: str) -> UserModel | None:
        """Retrieve a user model by ID.

        Args:
            user_id: Unique user identifier

        Returns:
            UserModel if found, None otherwise
        """
        pass

    @abstractmethod
    async def save(self, model: UserModel) -> None:
        """Save a user model.

        Args:
            model: UserModel to save
        """
        pass

    @abstractmethod
    async def delete(self, user_id: str) -> None:
        """Delete a user model.

        Args:
            user_id: User ID to delete
        """
        pass

    @abstractmethod
    async def list_users(self, limit: int = 100, offset: int = 0) -> list[str]:
        """List all user IDs.

        Args:
            limit: Maximum number of users to return
            offset: Offset for pagination

        Returns:
            List of user IDs
        """
        pass


class InMemoryUserModelStorage(UserModelStorage):
    """In-memory storage implementation for user models."""

    def __init__(self):
        self._storage: dict[str, UserModel] = {}

    async def get(self, user_id: str) -> UserModel | None:
        return self._storage.get(user_id)

    async def save(self, model: UserModel) -> None:
        self._storage[model.user_id] = model

    async def delete(self, user_id: str) -> None:
        self._storage.pop(user_id, None)

    async def list_users(self, limit: int = 100, offset: int = 0) -> list[str]:
        all_users = list(self._storage.keys())
        return all_users[offset : offset + limit]


# ============================================================================
# Adaptive User Modeling System
# ============================================================================


class AdaptiveUserModeling:
    """Adaptive user modeling with real-time learning.

    This class implements the core adaptive user modeling logic inspired by
    Honcho's approach: treating memory as reasoning rather than storage.

    Key features:
    - Formal logic conclusion extraction (deductive/inductive/abductive)
    - Preference learning with confidence tracking
    - Emotional trigger detection
    - Relationship metrics (trust, familiarity)
    - Query interface for retrieving user insights
    """

    def __init__(
        self,
        llm_client: LLMClient,
        storage: UserModelStorage | None = None,
    ):
        """Initialize adaptive user modeling.

        Args:
            llm_client: LLM client for reasoning and extraction
            storage: Optional storage backend (defaults to in-memory)
        """
        self.llm_client = llm_client
        self.storage = storage or InMemoryUserModelStorage()
        self._cache: dict[str, UserModel] = {}  # Local cache

    async def get_or_create_user(self, user_id: str) -> UserModel:
        """Get existing user model or create new one.

        Args:
            user_id: Unique user identifier

        Returns:
            UserModel instance
        """
        # Check cache first
        if user_id in self._cache:
            return self._cache[user_id]

        # Try storage
        model = await self.storage.get(user_id)
        if model is None:
            # Create new model
            model = UserModel(user_id=user_id)
            await self.storage.save(model)
            logger.info(f"Created new user model for {user_id}")

        # Cache and return
        self._cache[user_id] = model
        return model

    async def update_from_interaction(
        self,
        user_id: str,
        user_message: str,
        assistant_message: str,
        emotional_state: Any | None = None,
        interaction_id: str = "",
    ) -> UserModel:
        """Update user model from an interaction.

        This is the main entry point for learning from user interactions.
        It performs multiple learning tasks in parallel:
        1. Extract explicit premises from message
        2. Generate conclusions (deductive/inductive/abductive)
        3. Update preferences if detected
        4. Detect emotional triggers
        5. Update relationship metrics
        6. Store updated model

        Args:
            user_id: User identifier
            user_message: User's message
            assistant_message: Assistant's response
            emotional_state: Optional emotional state during interaction
            interaction_id: Optional reference to the interaction

        Returns:
            Updated UserModel
        """
        model = await self.get_or_create_user(user_id)

        # Build context from current model
        context = await self._build_extraction_context(model)

        # Extract conclusions
        conclusions = await self.extract_conclusions(user_message, context, model)
        for conclusion in conclusions:
            conclusion.source_interaction = interaction_id
            model.add_conclusion(conclusion)

        # Detect preferences
        preferences = await self.detect_preferences(user_message, model)
        for pref in preferences:
            pref.learned_from = interaction_id
            model.add_preference(pref)

        # Detect emotional triggers
        triggers = await self.detect_emotional_triggers(user_message, emotional_state)
        for trigger, intensity in triggers.items():
            model.update_emotional_trigger(trigger, intensity)

        # Calculate interaction metrics
        sentiment = await self._analyze_sentiment(user_message)
        depth = self._calculate_interaction_depth(user_message)

        # Update relationship metrics
        model = self.update_relationship_metrics(model, sentiment, depth)

        # Record interaction pattern
        model.record_interaction(
            {
                "sentiment": sentiment,
                "depth": depth,
                "message_length": len(user_message),
                "has_question": "?" in user_message,
            }
        )

        # Save updated model
        await self.storage.save(model)
        self._cache[user_id] = model

        logger.debug(f"Updated user model for {user_id}")
        return model

    async def extract_conclusions(
        self,
        user_message: str,
        context: str,
        current_model: UserModel,
    ) -> list[Conclusion]:
        """Extract conclusions using formal logic reasoning.

        Uses the LLM to perform three types of reasoning:
        - Deductive: logical inferences from premises (general to specific)
        - Inductive: pattern recognition from observations (specific to general)
        - Abductive: best explanations for observations (inference to best explanation)

        Args:
            user_message: User's message
            context: Current context about the user
            current_model: Current user model

        Returns:
            List of Conclusion objects
        """
        prompt = f"""You are analyzing a user message to extract reasoned conclusions about them.

Current user context:
{context}

User message: "{user_message}"

Perform formal logic reasoning to extract conclusions:

1. DEDUCTIVE: If the user states general principles, what specific facts can we infer?
   Example: "I always eat vegan" → "User is vegan"

2. INDUCTIVE: From specific statements, what general patterns can we identify?
   Example: "I went hiking last weekend and the weekend before" → "User enjoys hiking regularly"

3. ABDUCTIVE: What are the best explanations for what the user is expressing?
   Example: "I'm exhausted from work" → "User may have a demanding job or be overworked"

Return ONLY a JSON object in this exact format:
{{
    "conclusions": [
        {{
            "type": "deductive|inductive|abductive",
            "premises": ["observed fact 1", "observed fact 2"],
            "conclusion": "the reasoned conclusion",
            "confidence": 0.8
        }}
    ]
}}

Important:
- Only include high-quality conclusions with clear reasoning
- Confidence should be 0.5-1.0 based on strength of evidence
- Premises should be actual observations from the message
- If no valid conclusions can be drawn, return empty list"""

        try:
            response = await self.llm_client.chat(
                messages=[
                    {"role": "system", "content": "You are a precise logical reasoning engine."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=1000,
            )

            # Parse JSON response
            content = response.content.strip()
            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            data = json.loads(content)
            conclusions = []

            for item in data.get("conclusions", []):
                conclusion = Conclusion(
                    conclusion_type=item.get("type", "inductive"),
                    premises=item.get("premises", []),
                    conclusion=item.get("conclusion", ""),
                    confidence=item.get("confidence", 0.5),
                )
                # Only include conclusions with reasonable confidence
                if conclusion.confidence >= 0.5:
                    conclusions.append(conclusion)

            return conclusions

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse conclusions JSON: {e}")
            return []
        except Exception as e:
            logger.error(f"Error extracting conclusions: {e}")
            return []

    async def detect_preferences(
        self,
        user_message: str,
        current_model: UserModel,
    ) -> list[UserPreference]:
        """Detect new or updated preferences from user message.

        Args:
            user_message: User's message
            current_model: Current user model

        Returns:
            List of detected UserPreference objects
        """
        prompt = f"""Analyze the user message to detect any preferences.

User message: "{user_message}"

Detect preferences in these categories:
- communication: How they like to communicate (direct, detailed, brief, formal, casual)
- content: What topics or content they prefer
- topic: Specific topics they enjoy or dislike
- style: Writing/communication style preferences
- interaction: How they prefer to interact (quick answers, detailed explanations, etc.)
- tone: Preferred tone (professional, friendly, humorous, serious)

Return ONLY a JSON object in this exact format:
{{
    "preferences": [
        {{
            "category": "communication|content|topic|style|interaction|tone",
            "value": "the specific preference",
            "confidence": 0.8,
            "evidence": "quote from message supporting this"
        }}
    ]
}}

Important:
- Only include preferences with clear evidence from the message
- Confidence should reflect how explicit the preference is
- If no preferences are detected, return empty list
- Be conservative - don't over-interpret"""

        try:
            response = await self.llm_client.chat(
                messages=[
                    {"role": "system", "content": "You are a preference detection system."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=800,
            )

            content = response.content.strip()
            # Remove markdown code blocks
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            data = json.loads(content)
            preferences = []

            for item in data.get("preferences", []):
                pref = UserPreference(
                    category=item.get("category", "general"),
                    value=item.get("value", ""),
                    confidence=item.get("confidence", 0.5),
                )
                # Only include high-confidence preferences
                if pref.confidence >= 0.6:
                    preferences.append(pref)

            return preferences

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse preferences JSON: {e}")
            return []
        except Exception as e:
            logger.error(f"Error detecting preferences: {e}")
            return []

    async def detect_emotional_triggers(
        self,
        user_message: str,
        emotional_state: Any | None = None,
    ) -> dict[str, float]:
        """Identify patterns that trigger emotional responses.

        Args:
            user_message: User's message
            emotional_state: Optional emotional state during interaction

        Returns:
            Dictionary mapping trigger topics to intensity scores
        """
        prompt = f"""Analyze the user message to identify emotional triggers.

User message: "{user_message}"

Identify:
1. Topics that seem to trigger strong emotions (positive or negative)
2. Patterns in language that indicate emotional significance
3. Subjects the user feels strongly about

Return ONLY a JSON object in this exact format:
{{
    "triggers": [
        {{
            "topic": "specific topic or subject",
            "intensity": 0.8,
            "sentiment": "positive|negative|mixed"
        }}
    ]
}}

Important:
- Intensity should be 0.0-1.0 based on emotional strength
- Be specific about topics (e.g., "work deadlines" not just "work")
- If no emotional triggers detected, return empty list"""

        try:
            response = await self.llm_client.chat(
                messages=[
                    {"role": "system", "content": "You are an emotional trigger detection system."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=600,
            )

            content = response.content.strip()
            # Remove markdown code blocks
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            data = json.loads(content)
            triggers = {}

            for item in data.get("triggers", []):
                topic = item.get("topic", "").lower().strip()
                intensity = item.get("intensity", 0.5)
                if topic and intensity >= 0.5:
                    triggers[topic] = intensity

            return triggers

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse triggers JSON: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error detecting emotional triggers: {e}")
            return {}

    def update_relationship_metrics(
        self,
        model: UserModel,
        interaction_sentiment: float,
        interaction_depth: float,
    ) -> UserModel:
        """Update trust_level and familiarity based on interaction.

        Trust increases with positive sentiment and self-disclosure.
        Familiarity increases with interaction count and depth.

        Args:
            model: UserModel to update
            interaction_sentiment: Sentiment score (-1.0 to 1.0)
            interaction_depth: Depth score (0.0 to 1.0)

        Returns:
            Updated UserModel
        """
        # Update trust
        # Trust grows with positive sentiment and decays with negative
        trust_delta = 0.0

        if interaction_sentiment > 0.3:
            # Positive interaction increases trust
            trust_delta = interaction_sentiment * 0.05
        elif interaction_sentiment < -0.3:
            # Negative interaction decreases trust
            trust_delta = interaction_sentiment * 0.08  # Penalize more than reward

        # Depth increases trust (self-disclosure signals trust)
        if interaction_depth > 0.6:
            trust_delta += 0.02

        model.trust_level = max(0.0, min(1.0, model.trust_level + trust_delta))

        # Update familiarity
        # Familiarity grows with each interaction, faster with depth
        familiarity_delta = 0.01 + (interaction_depth * 0.02)
        model.familiarity = max(0.0, min(1.0, model.familiarity + familiarity_delta))

        model.updated_at = datetime.now()

        return model

    async def query_user_preferences(
        self,
        user_id: str,
        query: str,
    ) -> str:
        """Query the user model for preferences (like Honcho's chat API).

        Returns natural language answer about user preferences based on
        the stored conclusions and preferences.

        Args:
            user_id: User identifier
            query: Natural language query about preferences

        Returns:
            Natural language answer
        """
        model = await self.get_or_create_user(user_id)

        # Build context from user model
        context_lines = ["What I know about this user:"]

        # Add peer card facts
        if model.peer_card.facts:
            context_lines.append("\nKey facts:")
            for fact in model.peer_card.facts[:10]:
                context_lines.append(f"- {fact}")

        # Add high-confidence preferences
        high_conf_prefs = [p for p in model.preferences.values() if p.confidence >= 0.6]
        if high_conf_prefs:
            context_lines.append("\nPreferences:")
            for pref in sorted(high_conf_prefs, key=lambda x: -x.confidence)[:10]:
                context_lines.append(f"- {pref.category}: {pref.value}")

        # Add high-confidence conclusions
        high_conf_conclusions = [c for c in model.conclusions if c.confidence >= 0.7]
        if high_conf_conclusions:
            context_lines.append("\nConclusions:")
            for conclusion in sorted(high_conf_conclusions, key=lambda x: -x.confidence)[:5]:
                context_lines.append(f"- {conclusion.conclusion}")

        context = "\n".join(context_lines)

        prompt = f"""Based on the following information about a user, answer their question.

{context}

User question: "{query}"

Provide a helpful, accurate answer based ONLY on the information provided.
If the information doesn't contain an answer, say "I don't have enough information about that yet."
Be concise but informative."""

        try:
            response = await self.llm_client.chat(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant answering questions about user preferences.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=500,
            )
            return response.content.strip()

        except Exception as e:
            logger.error(f"Error querying user preferences: {e}")
            return "I'm unable to answer that question at the moment."

    async def build_user_context(
        self,
        user_id: str,
        max_tokens: int = 1000,
    ) -> str:
        """Build context string for prompt enhancement.

        Includes peer card facts, relevant conclusions, and active preferences
        formatted for LLM consumption.

        Args:
            user_id: User identifier
            max_tokens: Approximate token budget for context

        Returns:
            Formatted context string
        """
        model = await self.get_or_create_user(user_id)

        lines = ["## User Profile"]

        # Add relationship context
        lines.append(
            f"\nRelationship: trust={model.trust_level:.2f}, familiarity={model.familiarity:.2f}"
        )
        if model.preferred_style:
            lines.append(f"Preferred style: {model.preferred_style}")

        # Add peer card facts (most important)
        if model.peer_card.facts:
            lines.append("\n### Key Facts")
            # Include up to 15 facts, prioritizing recent ones
            for fact in model.peer_card.facts[-15:]:
                lines.append(f"- {fact}")

        # Add high-confidence preferences
        sorted_prefs = sorted(
            model.preferences.values(), key=lambda p: (-p.confidence, -p.evidence_count)
        )
        active_prefs = [p for p in sorted_prefs if p.confidence >= 0.5][:10]

        if active_prefs:
            lines.append("\n### Preferences")
            for pref in active_prefs:
                lines.append(pref.to_prompt_context())

        # Add recent high-confidence conclusions
        recent_conclusions = [c for c in model.conclusions if c.confidence >= 0.6][-5:]

        if recent_conclusions:
            lines.append("\n### Insights")
            for conclusion in recent_conclusions:
                lines.append(f"- {conclusion.to_prompt_context()}")

        # Add emotional triggers if any are significant
        significant_triggers = {k: v for k, v in model.emotional_triggers.items() if v >= 0.6}
        if significant_triggers:
            lines.append("\n### Sensitive Topics")
            for trigger, intensity in sorted(significant_triggers.items(), key=lambda x: -x[1]):
                lines.append(f"- {trigger} (intensity: {intensity:.2f})")

        context = "\n".join(lines)

        # Rough token estimation (4 chars ≈ 1 token)
        estimated_tokens = len(context) / 4
        if estimated_tokens > max_tokens:
            # Truncate by removing less important sections
            lines = ["## User Profile"]
            lines.append(
                f"Relationship: trust={model.trust_level:.2f}, familiarity={model.familiarity:.2f}"
            )

            if model.peer_card.facts:
                lines.append("\n### Key Facts")
                for fact in model.peer_card.facts[-8:]:  # Reduce facts
                    lines.append(f"- {fact}")

            if active_prefs[:5]:  # Reduce preferences
                lines.append("\n### Preferences")
                for pref in active_prefs[:5]:
                    lines.append(pref.to_prompt_context())

            context = "\n".join(lines)

        return context

    # ============================================================================
    # Helper Methods
    # ============================================================================

    async def _build_extraction_context(self, model: UserModel) -> str:
        """Build context string for extraction operations."""
        lines = []

        if model.peer_card.facts:
            lines.append("Known facts:")
            for fact in model.peer_card.facts[-10:]:
                lines.append(f"- {fact}")

        if model.preferences:
            lines.append("\nKnown preferences:")
            for pref in list(model.preferences.values())[-5:]:
                lines.append(f"- {pref.category}: {pref.value}")

        return "\n".join(lines) if lines else "No prior information about this user."

    async def _analyze_sentiment(self, message: str) -> float:
        """Analyze sentiment of a message (-1.0 to 1.0).

        Uses a simple LLM-based sentiment analysis.
        """
        prompt = f"""Analyze the sentiment of this message. Return ONLY a number from -1.0 (very negative) to 1.0 (very positive), where 0.0 is neutral.

Message: "{message}"

Sentiment score:"""

        try:
            response = await self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10,
            )

            content = response.content.strip()
            # Extract number from response
            import re

            match = re.search(r"-?\d+\.?\d*", content)
            if match:
                sentiment = float(match.group())
                return max(-1.0, min(1.0, sentiment))
            return 0.0

        except Exception as e:
            logger.warning(f"Sentiment analysis failed: {e}")
            return 0.0

    def _calculate_interaction_depth(self, message: str) -> float:
        """Calculate interaction depth score based on message characteristics.

        Depth indicators:
        - Message length (longer = more disclosure)
        - Personal pronouns (I, me, my)
        - Emotional language
        - Questions asked (seeking connection)
        """
        depth = 0.0

        # Length factor (normalized, max at 200 chars)
        length_factor = min(len(message) / 200, 1.0)
        depth += length_factor * 0.3

        # Personal disclosure (presence of personal pronouns)
        personal_words = ["i ", "me ", "my ", "mine", "myself"]
        personal_count = sum(1 for word in personal_words if word in message.lower())
        disclosure_factor = min(personal_count / 3, 1.0)
        depth += disclosure_factor * 0.4

        # Emotional content
        emotional_words = [
            "feel",
            "feeling",
            "felt",
            "happy",
            "sad",
            "angry",
            "worried",
            "excited",
            "love",
            "hate",
            "enjoy",
            "upset",
            "grateful",
            "frustrated",
            "anxious",
            "hopeful",
        ]
        emotional_count = sum(1 for word in emotional_words if word in message.lower())
        emotional_factor = min(emotional_count / 2, 1.0)
        depth += emotional_factor * 0.3

        return min(depth, 1.0)

    async def get_user_summary(self, user_id: str) -> dict[str, Any]:
        """Get a summary of the user model.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with user summary
        """
        model = await self.get_or_create_user(user_id)

        return {
            "user_id": model.user_id,
            "relationship": {
                "trust_level": round(model.trust_level, 2),
                "familiarity": round(model.familiarity, 2),
                "interaction_count": model.interaction_count,
            },
            "peer_card": {
                "fact_count": len(model.peer_card.facts),
                "facts": model.peer_card.facts[-10:],
            },
            "preferences": {
                "total": len(model.preferences),
                "by_category": {
                    cat: len(model.get_preferences_by_category(cat))
                    for cat in set(p.category for p in model.preferences.values())
                },
            },
            "conclusions": len(model.conclusions),
            "emotional_triggers": len(model.emotional_triggers),
            "first_interaction": model.first_interaction_at.isoformat(),
            "last_interaction": model.last_interaction_at.isoformat()
            if model.last_interaction_at
            else None,
        }


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "Conclusion",
    "UserPeerCard",
    "UserPreference",
    "UserModel",
    "UserModelStorage",
    "InMemoryUserModelStorage",
    "AdaptiveUserModeling",
]
