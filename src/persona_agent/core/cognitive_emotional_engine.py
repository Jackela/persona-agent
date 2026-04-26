"""Cognitive-Emotional Dual-Path Architecture for Persona-Agent.

This module implements a dual-path processing system inspired by EmotionFlow (MIT 2024),
where cognitive and emotional pathways operate in parallel and merge through a fusion layer.

Key Concepts:
- Valence-Arousal-Dominance (VAD) model for emotional states
- Multi-emotion detection with intensity blends
- Cognitive-emotional fusion with affect influence modulation
- Temporal decay and state transitions for emotional persistence
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from typing import TYPE_CHECKING, Any

from persona_agent.core.schemas import (
    CognitiveOutput,
    EmotionalOutput,
    EmotionalState,
    FusedState,
    WorkingMemory,
)

if TYPE_CHECKING:
    from persona_agent.utils.llm_client import LLMClient


# ============================================================================
# Emotional Constants and Utilities
# ============================================================================

# Valence-Arousal-Dominance mappings for common emotions
# Based on the Circumplex Model of Affect
EMOTION_VAD_MAP: dict[str, tuple[float, float, float]] = {
    # (valence, arousal, dominance)
    "neutral": (0.0, 0.5, 0.5),
    "happy": (0.8, 0.6, 0.6),
    "joy": (0.9, 0.7, 0.7),
    "excited": (0.8, 0.9, 0.7),
    "content": (0.7, 0.3, 0.6),
    "sad": (-0.7, 0.3, 0.3),
    "depressed": (-0.8, 0.2, 0.2),
    "melancholy": (-0.4, 0.3, 0.4),
    "angry": (-0.7, 0.8, 0.8),
    "furious": (-0.9, 0.95, 0.9),
    "irritated": (-0.5, 0.6, 0.6),
    "afraid": (-0.7, 0.8, 0.2),
    "anxious": (-0.6, 0.75, 0.3),
    "worried": (-0.5, 0.6, 0.4),
    "scared": (-0.8, 0.85, 0.15),
    "surprised": (0.2, 0.8, 0.5),
    "disgusted": (-0.6, 0.5, 0.5),
    "contemptuous": (-0.5, 0.4, 0.7),
    "ashamed": (-0.6, 0.4, 0.2),
    "guilty": (-0.5, 0.5, 0.3),
    "embarrassed": (-0.4, 0.6, 0.2),
    "proud": (0.7, 0.6, 0.8),
    "confident": (0.6, 0.5, 0.85),
    "hopeful": (0.6, 0.5, 0.6),
    "loving": (0.9, 0.5, 0.5),
    "grateful": (0.8, 0.4, 0.5),
    "jealous": (-0.5, 0.6, 0.4),
    "curious": (0.3, 0.7, 0.6),
    "bored": (-0.3, 0.2, 0.4),
    "tired": (-0.2, 0.15, 0.3),
    "relaxed": (0.5, 0.2, 0.5),
    "calm": (0.4, 0.1, 0.5),
}

# Response tone mappings based on VAD coordinates
TONE_MAPPINGS: list[tuple[tuple[float, float, float], str]] = [
    # ((valence_threshold, arousal_threshold, dominance_threshold), tone)
    ((0.6, 0.7, 0.5), "enthusiastic"),
    ((0.5, 0.3, 0.5), "warm"),
    ((0.3, 0.7, 0.6), "energetic"),
    ((-0.5, 0.7, 0.6), "assertive"),
    ((-0.5, 0.7, 0.4), "defensive"),
    ((-0.6, 0.4, 0.3), "somber"),
    ((-0.4, 0.6, 0.4), "concerned"),
    ((-0.7, 0.8, 0.2), "fearful"),
    ((0.7, 0.3, 0.7), "confident"),
    ((0.0, 0.5, 0.5), "neutral"),
]


def vad_to_emotion_label(valence: float, arousal: float, dominance: float) -> str:
    """Convert VAD coordinates to nearest emotion label.

    Args:
        valence: Pleasure level (-1.0 to 1.0)
        arousal: Activation level (0.0 to 1.0)
        dominance: Control level (0.0 to 1.0)

    Returns:
        Closest matching emotion label
    """
    min_distance = float("inf")
    closest_emotion = "neutral"

    for emotion, (e_v, e_a, e_d) in EMOTION_VAD_MAP.items():
        # Euclidean distance in 3D VAD space
        distance = math.sqrt((valence - e_v) ** 2 + (arousal - e_a) ** 2 + (dominance - e_d) ** 2)
        if distance < min_distance:
            min_distance = distance
            closest_emotion = emotion

    return closest_emotion


def interpolate_vad(emotions: list[dict[str, Any]]) -> tuple[float, float, float, list[str]]:
    """Interpolate VAD coordinates from multiple emotions with intensities.

    Args:
        emotions: List of dicts with 'label', 'intensity', and optionally
                  'valence', 'arousal', 'dominance' keys.
                  Example: [{"label": "happy", "intensity": 0.8}, ...]

    Returns:
        Tuple of (valence, arousal, dominance, secondary_labels)
    """
    total_weight = 0.0
    weighted_valence = 0.0
    weighted_arousal = 0.0
    weighted_dominance = 0.0

    for emotion in emotions:
        label = emotion.get("label", "neutral")
        intensity = emotion.get("intensity", 0.5)

        # Get VAD from map or use defaults
        if label in EMOTION_VAD_MAP:
            v, a, d = EMOTION_VAD_MAP[label]
        else:
            # Use custom VAD if provided
            v = emotion.get("valence", 0.0)
            a = emotion.get("arousal", 0.5)
            d = emotion.get("dominance", 0.5)

        weighted_valence += v * intensity
        weighted_arousal += a * intensity
        weighted_dominance += d * intensity
        total_weight += intensity

    if total_weight == 0:
        return 0.0, 0.5, 0.5, []

    # Normalize
    valence = max(-1.0, min(1.0, weighted_valence / total_weight))
    arousal = max(0.0, min(1.0, weighted_arousal / total_weight))
    dominance = max(0.0, min(1.0, weighted_dominance / total_weight))

    # Get secondary emotions (those with significant but lower intensity)
    secondary = [
        e["label"]
        for e in emotions
        if e.get("intensity", 0.5) < 0.6 and e.get("intensity", 0.5) > 0.2
    ]

    return valence, arousal, dominance, secondary


def determine_response_tone(valence: float, arousal: float, dominance: float) -> str:
    """Determine appropriate response tone based on VAD state.

    Args:
        valence: Pleasure level (-1.0 to 1.0)
        arousal: Activation level (0.0 to 1.0)
        dominance: Control level (0.0 to 1.0)

    Returns:
        Recommended response tone descriptor
    """
    for (t_v, t_a, t_d), tone in TONE_MAPPINGS:
        if valence >= t_v and arousal >= t_a and dominance >= t_d:
            return tone
    return "neutral"


# ============================================================================
# Cognitive Pathway
# ============================================================================


class CognitivePathway:
    """Cognitive processing: understanding, reasoning, intent detection.

    The cognitive pathway focuses on:
    1. Extracting understanding of user input
    2. Identifying user intent (informational, emotional, action-oriented)
    3. Extracting topics and entities
    4. Generating reasoning about appropriate response
    5. Calculating relevance scores

    This pathway operates independently of emotional processing, providing
    a rational, analytical view of the interaction.
    """

    def __init__(self, llm_client: LLMClient):
        """Initialize cognitive pathway with LLM client.

        Args:
            llm_client: Client for LLM-based processing
        """
        self.llm_client = llm_client

    async def process(
        self,
        user_input: str,
        working_memory: WorkingMemory,
    ) -> CognitiveOutput:
        """Process user input through the cognitive pathway.

        This method performs comprehensive cognitive analysis:
        1. Extracts semantic understanding of user message
        2. Identifies user intent (what they want)
        3. Extracts key topics and entities
        4. Generates reasoning about context and appropriate response
        5. Calculates relevance score based on conversation context

        Args:
            user_input: The raw user input text
            working_memory: Recent conversation context

        Returns:
            CognitiveOutput containing all cognitive analysis results

        Example:
            >>> cognitive = CognitivePathway(llm_client)
            >>> output = await cognitive.process(
            ...     "I'm feeling really stressed about my project deadline",
            ...     working_memory
            ... )
            >>> print(output.user_intent)  # "seeking emotional support"
            >>> print(output.topics)  # ["work stress", "deadline pressure"]
        """
        # Build context from working memory
        context = self._build_context(working_memory)

        # Construct cognitive analysis prompt
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a cognitive analysis system. Analyze the user input "
                    "from a rational, analytical perspective. Focus on understanding "
                    "what the user is saying, their intent, and key topics/entities. "
                    "Do NOT consider emotional aspects - those will be handled separately.\n\n"
                    "Provide your analysis in this JSON format:\n"
                    "{\n"
                    '  "understanding": "A concise summary of what the user is communicating",\n'
                    '  "user_intent": "One of: informational_query, emotional_support, '
                    'action_request, social_chat, opinion_seeking, or other",\n'
                    '  "topics": ["list", "of", "main", "topics"],\n'
                    '  "entities": ["named", "entities", "mentioned"],\n'
                    '  "reasoning": "Your internal reasoning about appropriate response approach",\n'
                    '  "relevance_score": 0.0 to 1.0 based on coherence with conversation context\n'
                    "}"
                ),
            },
            {
                "role": "user",
                "content": f"Conversation context:\n{context}\n\nUser input: {user_input}",
            },
        ]

        # Get LLM response
        try:
            if self.llm_client is None:
                return self._fallback_cognitive_processing(user_input, working_memory)

            response = await self.llm_client.chat(
                messages,
                temperature=0.3,
                max_tokens=800,
            )

            # Parse JSON response
            analysis = self._parse_json_response(response.content)

            return CognitiveOutput(
                understanding=analysis.get("understanding", ""),
                relevance_score=analysis.get("relevance_score", 0.5),
                user_intent=analysis.get("user_intent", ""),
                topics=analysis.get("topics", []),
                entities=analysis.get("entities", []),
                reasoning=analysis.get("reasoning", ""),
            )

        except Exception:
            # Fallback to basic extraction if LLM fails
            return self._fallback_cognitive_processing(user_input, working_memory)

    def _build_context(self, working_memory: WorkingMemory) -> str:
        """Build string context from working memory.

        Args:
            working_memory: Working memory instance

        Returns:
            Formatted context string
        """
        recent_messages = working_memory.get_recent()
        if not recent_messages:
            return "No prior conversation context."
        lines = []
        for msg in recent_messages:
            # Handle both dict and Message objects
            if isinstance(msg, dict):
                role = "User" if msg.get("role") == "user" else "Assistant"
                content = msg.get("content", "")
            else:
                # Message dataclass
                role = "User" if msg.role == "user" else "Assistant"
                content = msg.content
            lines.append(f"{role}: {content}")

        return "\n".join(lines)

    def _parse_json_response(self, content: str) -> dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks.

        Args:
            content: Raw LLM response content

        Returns:
            Parsed dictionary
        """
        # Try to extract JSON from markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Return empty dict if parsing fails
            return {}

    def _fallback_cognitive_processing(
        self, user_input: str, working_memory: WorkingMemory
    ) -> CognitiveOutput:
        """Fallback processing when LLM fails.

        Args:
            user_input: User input text
            working_memory: Working memory

        Returns:
            Basic CognitiveOutput
        """
        # Basic keyword-based intent detection
        input_lower = user_input.lower()

        if any(w in input_lower for w in ["?", "what", "how", "why", "when", "where"]):
            intent = "informational_query"
        elif any(w in input_lower for w in ["help", "support", "feel", "stressed", "sad"]):
            intent = "emotional_support"
        elif any(w in input_lower for w in ["can you", "please", "do this", "make"]):
            intent = "action_request"
        else:
            intent = "social_chat"

        # Extract simple "entities" (capitalized words)
        import re

        entities = re.findall(r"\b[A-Z][a-z]+\b", user_input)

        return CognitiveOutput(
            understanding=f"User said: {user_input[:100]}...",
            relevance_score=0.5,
            user_intent=intent,
            topics=[],
            entities=list(set(entities))[:5],  # Limit to 5 unique entities
            reasoning="Fallback processing due to LLM failure",
        )


# ============================================================================
# Emotional Pathway
# ============================================================================


class EmotionalPathway:
    """Emotional processing: emotion detection, affect influence.

    The emotional pathway focuses on:
    1. Detecting emotions in user input (multi-emotion support)
    2. Calculating character's emotional reaction
    3. Determining appropriate response tone
    4. Calculating affect influence on cognition

    This pathway operates independently of cognitive processing, providing
    an affective view of the interaction.
    """

    # Emotional decay constants
    DEFAULT_DECAY_RATE = 0.05  # 5% decay per minute
    MINIMUM_INTENSITY = 0.1  # Below this, emotion considered neutral

    def __init__(self, llm_client: LLMClient):
        """Initialize emotional pathway with LLM client.

        Args:
            llm_client: Client for LLM-based emotion detection
        """
        self.llm_client = llm_client

    async def process(
        self,
        user_input: str,
        cognitive_output: CognitiveOutput,
        current_emotional_state: EmotionalState,
    ) -> EmotionalOutput:
        """Process emotional aspects of the interaction.

        This method performs comprehensive emotional analysis:
        1. Detects emotions in user input (supports multiple simultaneous emotions)
        2. Calculates the character's emotional reaction
        3. Determines appropriate response tone
        4. Calculates affect influence (how much emotion should modulate cognition)

        Args:
            user_input: The raw user input text
            cognitive_output: Output from cognitive pathway for context
            current_emotional_state: Current VAD-based emotional state

        Returns:
            EmotionalOutput containing all emotional analysis results

        Example:
            >>> emotional = EmotionalPathway(llm_client)
            >>> output = await emotional.process(
            ...     "I just got promoted!",
            ...     cognitive_output,
            ...     current_emotional_state
            ... )
            >>> print(output.detected_emotions)  # [{"label": "joy", "intensity": 0.9}, ...]
            >>> print(output.emotional_reaction)  # "feeling happy and proud"
        """
        # Build emotional context
        context = self._build_emotional_context(cognitive_output, current_emotional_state)

        # Construct emotion analysis prompt
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an emotional analysis system. Analyze the emotional content "
                    "of the user input from the perspective of a character responding to them.\n\n"
                    "IMPORTANT: Support MULTIPLE simultaneous emotions. People often feel "
                    "blends of emotions (e.g., happy but nervous, angry but sad).\n\n"
                    "Provide your analysis in this JSON format:\n"
                    "{\n"
                    '  "detected_emotions": [\n'
                    '    {"label": "emotion_name", "intensity": 0.0-1.0, '
                    '"valence": -1.0-1.0, "arousal": 0.0-1.0, "dominance": 0.0-1.0},\n'
                    "    ... (can have multiple emotions)\n"
                    "  ],\n"
                    '  "emotional_reaction": "How the character feels in response",\n'
                    '  "appropriate_response_tone": "e.g., warm, excited, somber, concerned",\n'
                    '  "affect_influence": 0.0-1.0 (how much emotion should influence the response)\n'
                    "}\n\n"
                    "Common emotions: happy, sad, angry, afraid, surprised, disgusted, "
                    "joy, excitement, anxiety, pride, shame, guilt, love, gratitude, "
                    "jealousy, curiosity, boredom, relaxation"
                ),
            },
            {
                "role": "user",
                "content": f"{context}\n\nUser input: {user_input}",
            },
        ]

        # Get LLM response
        try:
            if self.llm_client is None:
                return self._fallback_emotional_processing(user_input, current_emotional_state)

            response = await self.llm_client.chat(
                messages,
                temperature=0.4,
                max_tokens=800,
            )

            # Parse JSON response
            analysis = self._parse_json_response(response.content)

            detected_emotions = analysis.get("detected_emotions", [])

            # Calculate VAD from detected emotions if not provided
            if detected_emotions and not all(
                "valence" in e and "arousal" in e for e in detected_emotions
            ):
                v, a, d, secondary = interpolate_vad(detected_emotions)

                # Update emotions with VAD if missing
                for emotion in detected_emotions:
                    if emotion.get("label") == detected_emotions[0].get("label"):
                        emotion.setdefault("valence", v)
                        emotion.setdefault("arousal", a)
                        emotion.setdefault("dominance", d)

            return EmotionalOutput(
                detected_emotions=detected_emotions,
                emotional_reaction=analysis.get("emotional_reaction", ""),
                appropriate_response_tone=analysis.get("appropriate_response_tone", "neutral"),
                affect_influence=analysis.get("affect_influence", 0.5),
            )

        except (RuntimeError, ValueError, TypeError):
            # Fallback to basic emotion processing
            return self._fallback_emotional_processing(user_input, current_emotional_state)

    def update_emotional_state(
        self,
        current: EmotionalState,
        emotional_output: EmotionalOutput,
        time_delta: float,
    ) -> EmotionalState:
        """Update emotional state based on new emotional output and time decay.

        This method implements:
        1. Valence shift based on interaction (emotional contagion)
        2. Arousal modulation based on emotional intensity
        3. Natural decay of emotions over time
        4. Intensity changes based on new emotional input

        Args:
            current: Current emotional state (VAD model)
            emotional_output: Output from emotional pathway processing
            time_delta: Time elapsed since last update (in seconds)

        Returns:
            Updated emotional state

        Example:
            >>> new_state = pathway.update_emotional_state(
            ...     current_state,
            ...     emotional_output,
            ...     time_delta=120.0  # 2 minutes passed
            ... )
        """
        # Calculate decay factor based on time passed
        # Decay rate per second (exponential decay)
        decay_per_second = self.DEFAULT_DECAY_RATE / 60.0  # Convert to per-second
        decay_factor = math.exp(-decay_per_second * time_delta)

        # Apply decay to current state's intensity
        decayed_intensity = current.intensity * decay_factor

        # Calculate new emotional impulse from detected emotions
        if emotional_output.detected_emotions:
            # Use primary emotion for state update
            primary = emotional_output.detected_emotions[0]
            new_valence = primary.get("valence", current.valence)
            new_arousal = primary.get("arousal", current.arousal)
            new_dominance = primary.get("dominance", current.dominance)
            new_intensity = primary.get("intensity", 0.5)
            primary_label = primary.get("label", "neutral")
        else:
            # No emotions detected, just decay toward neutral
            new_valence = 0.0
            new_arousal = 0.5
            new_dominance = 0.5
            new_intensity = 0.0
            primary_label = "neutral"

        # Calculate emotional momentum (how much the new emotion affects current state)
        # This simulates emotional inertia - we don't change instantly
        momentum = 0.4  # 40% current state, 60% new emotion

        # Blend current state with new emotional impulse
        blended_valence = (current.valence * momentum) + (new_valence * (1 - momentum))
        blended_arousal = (current.arousal * momentum) + (new_arousal * (1 - momentum))
        blended_dominance = (current.dominance * momentum) + (new_dominance * (1 - momentum))

        # Update intensity with some decay
        intensity_boost = new_intensity * 0.3  # New emotions boost intensity
        blended_intensity = min(1.0, decayed_intensity * 0.7 + intensity_boost)

        # Ensure values stay in bounds
        final_valence = max(-1.0, min(1.0, blended_valence))
        final_arousal = max(0.0, min(1.0, blended_arousal))
        final_dominance = max(0.0, min(1.0, blended_dominance))
        final_intensity = max(0.0, min(1.0, blended_intensity))

        # Determine primary and secondary emotions
        if emotional_output.detected_emotions and len(emotional_output.detected_emotions) > 1:
            secondary = [
                e["label"]
                for e in emotional_output.detected_emotions[1:]
                if e.get("intensity", 0) > 0.2
            ][
                :3
            ]  # Keep top 3 secondary emotions
        else:
            secondary = []

        # If intensity is too low, revert to neutral
        if final_intensity < self.MINIMUM_INTENSITY:
            primary_label = "neutral"
            secondary = []

        return EmotionalState(
            valence=final_valence,
            arousal=final_arousal,
            dominance=final_dominance,
            primary_emotion=str(primary_label),
            secondary_emotions=[str(s) for s in secondary] if secondary else [],
            intensity=final_intensity,
            entered_at=datetime.now(),
            duration_seconds=current.duration_seconds + time_delta,
        )

    def _build_emotional_context(
        self,
        cognitive_output: CognitiveOutput,
        current_emotional_state: EmotionalState,
    ) -> str:
        """Build emotional context for prompt.

        Args:
            cognitive_output: Cognitive processing output
            current_emotional_state: Current emotional state

        Returns:
            Context string
        """
        lines = [
            "Current character emotional state:",
            f"- Primary emotion: {current_emotional_state.primary_emotion}",
            f"- Valence: {current_emotional_state.valence:.2f} (pleasantness)",
            f"- Arousal: {current_emotional_state.arousal:.2f} (activation)",
            f"- Dominance: {current_emotional_state.dominance:.2f} (control)",
            f"- Intensity: {current_emotional_state.intensity:.2f}",
            "",
            "Cognitive context:",
            f"- User intent: {cognitive_output.user_intent}",
            f"- Topics: {', '.join(cognitive_output.topics) if cognitive_output.topics else 'N/A'}",
        ]
        return "\n".join(lines)

    def _parse_json_response(self, content: str) -> dict[str, Any]:
        """Parse JSON from LLM response.

        Args:
            content: Raw response content

        Returns:
            Parsed dictionary
        """
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {}

    def _fallback_emotional_processing(
        self, user_input: str, current_state: EmotionalState
    ) -> EmotionalOutput:
        """Fallback when LLM fails.

        Args:
            user_input: User input text
            current_state: Current emotional state

        Returns:
            Basic EmotionalOutput
        """
        input_lower = user_input.lower()

        # Simple keyword-based emotion detection
        emotions = []

        positive_words = ["happy", "joy", "great", "excellent", "love", "wonderful", "!"]
        negative_words = ["sad", "angry", "hate", "terrible", "awful", "bad"]
        anxious_words = ["worried", "anxious", "nervous", "scared", "afraid"]

        if any(w in input_lower for w in positive_words):
            emotions.append({"label": "joy", "intensity": 0.7})
        if any(w in input_lower for w in negative_words):
            emotions.append({"label": "sadness", "intensity": 0.6})
        if any(w in input_lower for w in anxious_words):
            emotions.append({"label": "anxiety", "intensity": 0.7})

        if not emotions:
            emotions.append({"label": "neutral", "intensity": 0.3})

        # Character's reaction
        if emotions[0]["label"] in ["joy", "happy"]:
            reaction = "feeling happy for the user"
            tone = "warm"
        elif emotions[0]["label"] in ["sadness", "sad"]:
            reaction = "feeling concerned and empathetic"
            tone = "somber"
        elif emotions[0]["label"] == "anxiety":
            reaction = "feeling concerned and wanting to help"
            tone = "concerned"
        else:
            reaction = "remaining neutral"
            tone = "neutral"

        return EmotionalOutput(
            detected_emotions=emotions,
            emotional_reaction=reaction,
            appropriate_response_tone=tone,
            affect_influence=0.4 if emotions[0]["label"] != "neutral" else 0.2,
        )


# ============================================================================
# Fusion Layer
# ============================================================================


class FusionLayer:
    """Fuse cognitive and emotional outputs into unified state.

    The fusion layer is responsible for:
    1. Combining cognitive understanding with emotional context
    2. Applying emotional modulation to reasoning
    3. Generating response guidance that balances rational and affective needs
    4. Updating the fused emotional state

    This is where the dual paths converge into a unified representation
    that guides response generation.
    """

    def merge(
        self,
        cognitive: CognitiveOutput,
        emotional: EmotionalOutput,
        current_state: EmotionalState,
    ) -> FusedState:
        """Merge cognitive and emotional pathways into unified state.

        This method implements the fusion logic:
        1. Weighs cognitive understanding against emotional context
        2. Applies affect influence to modulate reasoning
        3. Generates response guidance combining both perspectives
        4. Updates the fused emotional state with new information

        The fusion formula considers:
        - Affect influence: How much emotion should modulate cognition
        - User intent: What the user wants (from cognitive)
        - Detected emotions: What the user feels (from emotional)
        - Current state: The character's existing emotional state

        Args:
            cognitive: Output from cognitive pathway
            emotional: Output from emotional pathway
            current_state: Current emotional state before this interaction

        Returns:
            FusedState containing merged cognitive-emotional state

        Example:
            >>> fusion = FusionLayer()
            >>> fused = fusion.merge(
            ...     cognitive_output,
            ...     emotional_output,
            ...     current_emotional_state
            ... )
            >>> print(fused.response_guidance)
        """
        # Calculate fused emotional state
        fused_emotional_state = self._fuse_emotional_state(current_state, emotional)

        # Generate response guidance
        response_guidance = self._generate_response_guidance(
            cognitive, emotional, fused_emotional_state
        )

        return FusedState(
            cognitive=cognitive,
            emotional=emotional,
            fused_emotional_state=fused_emotional_state,
            response_guidance=response_guidance,
        )

    def _fuse_emotional_state(
        self,
        current_state: EmotionalState,
        emotional_output: EmotionalOutput,
    ) -> EmotionalState:
        """Calculate fused emotional state from current state and new output.

        Args:
            current_state: Current emotional state
            emotional_output: New emotional output

        Returns:
            Fused emotional state
        """
        # Start with current state as base
        if not emotional_output.detected_emotions:
            return current_state

        # Calculate weighted VAD from detected emotions
        detected = emotional_output.detected_emotions
        v, a, d, secondary = interpolate_vad(detected)

        # Blend with current state based on affect influence
        influence = emotional_output.affect_influence
        current_influence = 1.0 - influence

        fused_valence = (current_state.valence * current_influence) + (v * influence)
        fused_arousal = (current_state.arousal * current_influence) + (a * influence)
        fused_dominance = (current_state.dominance * current_influence) + (d * influence)

        # Update intensity based on emotional impact
        avg_intensity = sum(e.get("intensity", 0.5) for e in detected) / len(detected)
        fused_intensity = (current_state.intensity * 0.6) + (avg_intensity * 0.4)

        # Determine primary emotion from VAD
        primary_label = vad_to_emotion_label(fused_valence, fused_arousal, fused_dominance)

        return EmotionalState(
            valence=max(-1.0, min(1.0, fused_valence)),
            arousal=max(0.0, min(1.0, fused_arousal)),
            dominance=max(0.0, min(1.0, fused_dominance)),
            primary_emotion=primary_label,
            secondary_emotions=secondary[:3],  # Keep top 3
            intensity=max(0.0, min(1.0, fused_intensity)),
            entered_at=datetime.now(),
            duration_seconds=current_state.duration_seconds,
        )

    def _generate_response_guidance(
        self,
        cognitive: CognitiveOutput,
        emotional: EmotionalOutput,
        fused_state: EmotionalState,
    ) -> str:
        """Generate response guidance from fused state.

        Args:
            cognitive: Cognitive output
            emotional: Emotional output
            fused_state: Fused emotional state

        Returns:
            Response guidance string
        """
        guidance_parts = []

        # Add intent-based guidance
        if cognitive.user_intent:
            guidance_parts.append(f"User intent: {cognitive.user_intent}")

        # Add emotional context
        if fused_state.primary_emotion != "neutral":
            guidance_parts.append(
                f"Character is feeling {fused_state.primary_emotion} "
                f"(intensity: {fused_state.intensity:.1f})"
            )

        # Add response tone guidance
        tone = emotional.appropriate_response_tone or determine_response_tone(
            fused_state.valence,
            fused_state.arousal,
            fused_state.dominance,
        )
        guidance_parts.append(f"Response tone: {tone}")

        # Add affect influence guidance
        if emotional.affect_influence > 0.6:
            guidance_parts.append("High emotional influence - prioritize emotional resonance")
        elif emotional.affect_influence < 0.3:
            guidance_parts.append("Low emotional influence - prioritize factual accuracy")
        else:
            guidance_parts.append("Balanced approach - blend facts with emotional awareness")

        # Add reasoning guidance
        if cognitive.reasoning:
            guidance_parts.append(f"Reasoning: {cognitive.reasoning}")

        return "\n".join(guidance_parts)


# ============================================================================
# Main Cognitive-Emotional Engine
# ============================================================================


class CognitiveEmotionalEngine:
    """Main engine coordinating cognitive and emotional processing.

    The CognitiveEmotionalEngine orchestrates the dual-path architecture:
    1. Runs cognitive pathway to understand user input
    2. Runs emotional pathway to detect and react to emotions
    3. Updates emotional state with time-based decay
    4. Fuses outputs through the fusion layer
    5. Returns fused state for response generation

    This engine implements the complete EmotionFlow-inspired architecture
    with proper separation of concerns between cognitive and emotional processing.

    Attributes:
        llm_client: Client for LLM-based processing
        cognitive_pathway: CognitivePathway instance
        emotional_pathway: EmotionalPathway instance
        fusion_layer: FusionLayer instance
        emotional_state: Current emotional state (VAD model)
        last_update_time: Timestamp of last emotional state update

    Example:
        >>> engine = CognitiveEmotionalEngine(llm_client)
        >>> fused = await engine.process("I'm so excited about this!", working_memory)
        >>> print(fused.fused_emotional_state.primary_emotion)
        'excited'
    """

    def __init__(
        self,
        llm_client: LLMClient,
        initial_emotional_state: EmotionalState | None = None,
    ):
        """Initialize the cognitive-emotional engine.

        Args:
            llm_client: LLM client for cognitive and emotional processing
            initial_emotional_state: Optional starting emotional state.
                If not provided, defaults to neutral state.
        """
        self.llm_client = llm_client

        # Initialize pathway components
        self.cognitive_pathway = CognitivePathway(llm_client)
        self.emotional_pathway = EmotionalPathway(llm_client)
        self.fusion_layer = FusionLayer()

        # Initialize emotional state
        self.emotional_state = initial_emotional_state or create_neutral_emotional_state()
        self.last_update_time: datetime = datetime.now()

    async def process(
        self,
        user_input: str,
        working_memory: WorkingMemory,
    ) -> FusedState:
        """Process user input through the complete cognitive-emotional pipeline.

        This is the main entry point for processing. It:
        1. Calculates time delta since last update for proper decay
        2. Runs cognitive pathway to understand the input
        3. Runs emotional pathway to detect emotions
        4. Updates emotional state with decay and new emotions
        5. Fuses all outputs into unified state

        Args:
            user_input: The raw user input text
            working_memory: Recent conversation context

        Returns:
            FusedState containing all cognitive and emotional processing results

        Example:
            >>> engine = CognitiveEmotionalEngine(llm_client)
            >>> fused = await engine.process(
            ...     "I'm worried about my interview tomorrow",
            ...     working_memory
            ... )
            >>> print(fused.cognitive.user_intent)
            'emotional_support'
            >>> print(fused.fused_emotional_state.primary_emotion)
            'concerned'
        """
        # Calculate time delta for emotional decay
        current_time = datetime.now()
        time_delta = (current_time - self.last_update_time).total_seconds()
        self.last_update_time = current_time

        # Step 1: Run cognitive pathway (understanding, reasoning, intent)
        cognitive_output = await self.cognitive_pathway.process(user_input, working_memory)

        # Step 2: Run emotional pathway (emotion detection, reaction)
        emotional_output = await self.emotional_pathway.process(
            user_input,
            cognitive_output,
            self.emotional_state,
        )

        # Step 3: Update emotional state with decay and new emotions
        self.emotional_state = self.emotional_pathway.update_emotional_state(
            self.emotional_state,
            emotional_output,
            time_delta,
        )

        # Step 4: Fuse outputs through fusion layer
        fused_state = self.fusion_layer.merge(
            cognitive_output,
            emotional_output,
            self.emotional_state,
        )

        return fused_state

    def get_current_emotional_state(self) -> EmotionalState:
        """Get the current emotional state.

        Returns:
            Current EmotionalState (VAD model)
        """
        return self.emotional_state

    def reset_emotional_state(self, new_state: EmotionalState | None = None) -> None:
        """Reset emotional state to neutral or specified state.

        Args:
            new_state: Optional new emotional state. If None, resets to neutral.
        """
        self.emotional_state = new_state or create_neutral_emotional_state()
        self.last_update_time = datetime.now()

    def set_emotional_state(self, state: EmotionalState) -> None:
        """Directly set the emotional state (for testing or initialization).

        Args:
            state: New emotional state to set
        """
        self.emotional_state = state
        self.last_update_time = datetime.now()


# ============================================================================
# Utility Functions
# ============================================================================


def create_neutral_emotional_state() -> EmotionalState:
    """Create a neutral emotional state.

    Returns:
        EmotionalState with neutral VAD values
    """
    return EmotionalState(
        valence=0.0,
        arousal=0.5,
        dominance=0.5,
        primary_emotion="neutral",
        secondary_emotions=[],
        intensity=0.3,
    )


def emotional_distance(state1: EmotionalState, state2: EmotionalState) -> float:
    """Calculate distance between two emotional states in VAD space.

    Args:
        state1: First emotional state
        state2: Second emotional state

    Returns:
        Euclidean distance in 3D VAD space (0.0 to ~2.5)
    """
    return math.sqrt(
        (state1.valence - state2.valence) ** 2
        + (state1.arousal - state2.arousal) ** 2
        + (state1.dominance - state2.dominance) ** 2
    )


def emotional_similarity(state1: EmotionalState, state2: EmotionalState) -> float:
    """Calculate similarity between two emotional states.

    Args:
        state1: First emotional state
        state2: Second emotional state

    Returns:
        Similarity score from 0.0 (different) to 1.0 (identical)
    """
    max_distance = 2.5  # Approximate max distance in normalized VAD space
    distance = emotional_distance(state1, state2)
    return max(0.0, 1.0 - (distance / max_distance))


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Main classes
    "CognitivePathway",
    "EmotionalPathway",
    "FusionLayer",
    "CognitiveEmotionalEngine",
    # Constants and utilities
    "EMOTION_VAD_MAP",
    "TONE_MAPPINGS",
    "vad_to_emotion_label",
    "interpolate_vad",
    "determine_response_tone",
    "create_neutral_emotional_state",
    "emotional_distance",
    "emotional_similarity",
]
