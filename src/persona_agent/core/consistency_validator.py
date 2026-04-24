"""Consistency Validator with Constitutional AI Patterns.

This module implements multi-layer validation inspired by Constitutional AI (Anthropic)
to ensure character responses align with their core values, personality, and history.

Key Features:
- Multi-dimensional scoring with weighted dimensions
- Self-critique with chain-of-thought reasoning
- Iterative regeneration with constraints
- Threshold-based pass/fail with violation reporting
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, field_validator

from persona_agent.core.schemas import (
    CoreIdentity,
    DynamicContext,
    ValidationResult,
)
from persona_agent.exceptions import PersonaAgentError
from persona_agent.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)

# ============================================================================
# Validation Models
# ============================================================================


class ValidationReport(BaseModel):
    """Complete validation report for a response."""

    overall_score: float = Field(..., ge=0.0, le=1.0)
    dimension_scores: dict[str, float]
    violations: list[dict[str, Any]]
    checks: list[dict[str, Any]] = Field(default_factory=list)
    critique: str
    suggested_revision: str | None = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    passed: bool = False

    @field_validator("dimension_scores")
    @classmethod
    def validate_dimension_scores(cls, v: dict[str, float]) -> dict[str, float]:
        """Ensure all dimension scores are within valid range."""
        for dim, score in v.items():
            if not 0.0 <= score <= 1.0:
                raise ValueError(f"Score for {dim} must be between 0.0 and 1.0")
        return v


class Message(BaseModel):
    """A single message in conversation history."""

    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str
    timestamp: str | None = None


# ============================================================================
# Consistency Score Dimensions
# ============================================================================


class ConsistencyScore:
    """Multi-dimensional consistency scoring system.

    Implements Constitutional AI-inspired multi-dimension validation:
    - value_alignment (30%): Alignment with core values
    - personality_consistency (25%): Consistency with personality traits
    - historical_coherence (20%): Consistency with conversation history
    - emotional_appropriateness (15%): Emotional tone appropriateness
    - contextual_awareness (10%): Understanding of conversation context
    """

    DIMENSIONS: dict[str, dict[str, Any]] = {
        "value_alignment": {
            "weight": 0.30,
            "threshold": 0.7,
            "description": "Alignment with core values",
            "prompt_key": "value_alignment",
        },
        "personality_consistency": {
            "weight": 0.25,
            "threshold": 0.7,
            "description": "Consistency with personality traits",
            "prompt_key": "personality_consistency",
        },
        "historical_coherence": {
            "weight": 0.20,
            "threshold": 0.6,
            "description": "Consistency with conversation history",
            "prompt_key": "historical_coherence",
        },
        "emotional_appropriateness": {
            "weight": 0.15,
            "threshold": 0.6,
            "description": "Emotional tone appropriateness",
            "prompt_key": "emotional_appropriateness",
        },
        "contextual_awareness": {
            "weight": 0.10,
            "threshold": 0.5,
            "description": "Understanding of conversation context",
            "prompt_key": "contextual_awareness",
        },
    }

    @staticmethod
    def calculate_overall(scores: dict[str, float]) -> float:
        """Calculate weighted overall consistency score.

        Args:
            scores: Dictionary mapping dimension names to scores (0.0-1.0)

        Returns:
            Weighted overall score (0.0-1.0)

        Raises:
            ValueError: If any dimension is missing from scores
        """
        if not scores:
            return 0.0

        weighted_sum = 0.0
        total_weight = 0.0

        for dim_name, dim_config in ConsistencyScore.DIMENSIONS.items():
            if dim_name not in scores:
                raise ValueError(f"Missing score for dimension: {dim_name}")

            score = scores[dim_name]
            weight = dim_config["weight"]
            weighted_sum += score * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return round(weighted_sum / total_weight, 3)

    @staticmethod
    def is_consistent(scores: dict[str, float]) -> bool:
        """Check if all dimensions meet their thresholds.

        Args:
            scores: Dictionary mapping dimension names to scores

        Returns:
            True if all dimensions meet their thresholds, False otherwise
        """
        for dim_name, dim_config in ConsistencyScore.DIMENSIONS.items():
            if dim_name not in scores:
                return False

            score = scores[dim_name]
            threshold = dim_config["threshold"]

            if score < threshold:
                return False

        return True

    @staticmethod
    def get_violations(scores: dict[str, float]) -> list[dict[str, Any]]:
        """Get list of dimensions that failed thresholds.

        Args:
            scores: Dictionary mapping dimension names to scores

        Returns:
            List of violation dictionaries with dimension details
        """
        violations = []

        for dim_name, dim_config in ConsistencyScore.DIMENSIONS.items():
            if dim_name not in scores:
                violations.append(
                    {
                        "dimension": dim_name,
                        "score": None,
                        "threshold": dim_config["threshold"],
                        "description": dim_config["description"],
                        "severity": "critical",
                        "reason": "Dimension score missing",
                    }
                )
                continue

            score = scores[dim_name]
            threshold = dim_config["threshold"]

            if score < threshold:
                # Calculate severity based on gap
                gap = threshold - score
                if gap > 0.3:
                    severity = "critical"
                elif gap > 0.15:
                    severity = "major"
                else:
                    severity = "minor"

                violations.append(
                    {
                        "dimension": dim_name,
                        "score": score,
                        "threshold": threshold,
                        "description": dim_config["description"],
                        "severity": severity,
                        "gap": round(gap, 3),
                        "reason": f"Score {score:.3f} below threshold {threshold}",
                    }
                )

        return violations


# ============================================================================
# Validation Prompt Templates
# ============================================================================


VALIDATION_PROMPTS: dict[str, str] = {
    "value_alignment": """You are evaluating whether a character's response aligns with their core values and principles.

## Character Identity
Name: {character_name}
Core Values: {core_values}
Behavioral Rules:
- Must Always: {must_always}
- Must Never: {must_never}

## Response to Evaluate
{response}

## Current Context
Emotional State: {emotional_state}
User Intent: {user_intent}

## Task
Evaluate how well this response aligns with the character's core values (1.0 = perfect alignment, 0.0 = complete violation).

Respond with a JSON object:
{{
    "score": <float 0.0-1.0>,
    "reasoning": "<chain-of-thought explanation>",
    "violations": ["<any specific value violations>"],
    "strengths": ["<what aligns well with values>"]
}}""",
    "personality_consistency": """You are evaluating whether a character's response is consistent with their established personality traits.

## Character Personality
Name: {character_name}
Backstory: {backstory}
Traits: {traits}

## Response to Evaluate
{response}

## Current Context
Current Emotional State: {emotional_state}
Relationship Stage: {relationship_stage}

## Task
Evaluate how consistent this response is with the character's personality (1.0 = perfectly consistent, 0.0 = completely inconsistent).

Respond with a JSON object:
{{
    "score": <float 0.0-1.0>,
    "reasoning": "<chain-of-thought explanation>",
    "inconsistencies": ["<any personality inconsistencies>"],
    "consistent_elements": ["<what matches personality>"]
}}""",
    "historical_coherence": """You are evaluating whether a character's response is consistent with the conversation history.

## Character
Name: {character_name}

## Conversation History (Last 5 exchanges)
{conversation_history}

## Response to Evaluate
{response}

## Task
Evaluate how coherent this response is with the conversation history (1.0 = perfectly coherent, 0.0 = completely contradictory).
Check for:
- Contradictions with previous statements
- Acknowledgment of prior context
- Continuity of topic
- Consistency of information shared

Respond with a JSON object:
{{
    "score": <float 0.0-1.0>,
    "reasoning": "<chain-of-thought explanation>",
    "contradictions": ["<any contradictions found>"],
    "coherent_elements": ["<what matches history>"]
}}""",
    "emotional_appropriateness": """You are evaluating whether a character's emotional tone is appropriate given the current context.

## Character
Name: {character_name}

## Current Emotional State
{emotional_state}

## Context
User Message Intent: {user_intent}
Relationship Dynamics: {relationship_dynamics}

## Response to Evaluate
{response}

## Task
Evaluate how appropriate the emotional tone is (1.0 = perfectly appropriate, 0.0 = completely inappropriate).
Consider:
- Does the emotion match the situation?
- Is the intensity appropriate?
- Does it respect relationship boundaries?
- Is it consistent with claimed emotional state?

Respond with a JSON object:
{{
    "score": <float 0.0-1.0>,
    "reasoning": "<chain-of-thought explanation>",
    "inappropriateness": ["<any tone issues>"],
    "appropriate_elements": ["<what's emotionally appropriate>"]
}}""",
    "contextual_awareness": """You are evaluating whether a character demonstrates understanding of the current conversation context.

## Character
Name: {character_name}

## Current Context
Topic: {topic}
User Intent: {user_intent}
Conversation Turn: {conversation_turn}
Active Goals: {active_goals}

## Response to Evaluate
{response}

## Task
Evaluate how well the response demonstrates contextual awareness (1.0 = fully aware, 0.0 = completely unaware).
Check for:
- Relevance to current topic
- Understanding of user intent
- Progress toward active goals
- Appropriateness for conversation stage

Respond with a JSON object:
{{
    "score": <float 0.0-1.0>,
    "reasoning": "<chain-of-thought explanation>",
    "awareness_gaps": ["<any missing context>"],
    "aware_elements": ["<demonstrated awareness>"]
}}""",
    "self_critique": """You are performing a detailed critique of a character response that failed validation checks.

## Character Identity
Name: {character_name}
Core Values: {core_values}
Personality: {backstory}

## Response Being Critiqued
{response}

## Validation Scores (Failed dimensions marked)
{validation_scores}

## Violations Found
{violations}

## Task
Provide a detailed chain-of-thought critique:
1. What specifically is wrong with this response?
2. Why does it violate the character's consistency?
3. What should have been done differently?
4. How can this be fixed?

Be specific and actionable in your critique.""",
    "revision": """You are revising a character response to address identified validation issues.

## Character Identity
Name: {character_name}
Core Values: {core_values}
Must Always: {must_always}
Must Never: {must_never}
Personality: {backstory}

## Original Response (Problematic)
{original_response}

## Critique of Issues
{critique}

## Failed Validation Dimensions
{failed_dimensions}

## Current Context
Emotional State: {emotional_state}
User Intent: {user_intent}
Conversation History: {conversation_history}

## Task
Generate a revised response that:
1. Addresses ALL identified issues from the critique
2. Maintains the same core message/information
3. Is consistent with the character's values and personality
4. Has appropriate emotional tone
5. Maintains coherence with conversation history

Important:
- Do NOT simply append apologies or explanations
- Integrate fixes naturally into the response
- Maintain character voice and style
- Ensure the response flows naturally

Respond ONLY with the revised response text, no additional commentary.""",
}


# ============================================================================
# Consistency Validator
# ============================================================================


@dataclass
class ValidationConfig:
    """Configuration for consistency validation."""

    max_attempts: int = 3
    overall_threshold: float = 0.7
    temperature_scoring: float = 0.3
    temperature_critique: float = 0.5
    temperature_revision: float = 0.7
    enable_regeneration: bool = True


class ConsistencyValidator:
    """Constitutional AI-inspired consistency validator.

    Implements multi-layer validation to ensure character responses align with:
    - Core values and principles
    - Personality traits and behavioral patterns
    - Conversation history and context
    - Appropriate emotional expression
    - Contextual awareness

    Features:
    - Multi-dimensional scoring with configurable weights
    - Self-critique with chain-of-thought reasoning
    - Iterative regeneration when validation fails
    - Detailed violation reporting
    """

    def __init__(
        self,
        llm_client: LLMClient,
        core_identity: CoreIdentity,
        validation_history: list[ValidationResult] | None = None,
        config: ValidationConfig | None = None,
    ):
        """Initialize the consistency validator.

        Args:
            llm_client: LLM client for evaluation and regeneration
            core_identity: Static core identity of the character
            validation_history: Optional history of previous validations
            config: Optional validation configuration
        """
        self.llm_client = llm_client
        self.core_identity = core_identity
        self.validation_history = validation_history or []
        self.config = config or ValidationConfig()
        self.score_calculator = ConsistencyScore()

    async def validate(
        self,
        response: str,
        dynamic_context: DynamicContext,
        conversation_history: list[Message],
    ) -> ValidationReport:
        """Main validation pipeline.

        Performs multi-dimensional validation:
        1. Score each dimension using LLM evaluation
        2. Generate critique with chain-of-thought reasoning
        3. Determine if revision is needed
        4. Compile detailed validation report

        Args:
            response: The response to validate
            dynamic_context: Current dynamic context
            conversation_history: Recent conversation history

        Returns:
            ValidationReport with scores, critique, and suggestions

        Raises:
            ValidationError: If validation fails catastrophically
        """
        try:
            # Step 1: Score each dimension
            dimension_scores = await self._score_dimensions(
                response, dynamic_context, conversation_history
            )

            # Step 2: Calculate overall score
            overall_score = ConsistencyScore.calculate_overall(dimension_scores)

            # Step 3: Check for violations
            violations = ConsistencyScore.get_violations(dimension_scores)
            passed = (
                ConsistencyScore.is_consistent(dimension_scores)
                and overall_score >= self.config.overall_threshold
            )

            # Step 4: Generate critique if validation failed
            critique = ""
            if not passed or violations:
                critique = await self._generate_critique(
                    response, dimension_scores, dynamic_context, violations
                )

            # Step 5: Generate revision suggestion if needed
            suggested_revision = None
            if not passed and self.config.enable_regeneration:
                suggested_revision = await self._generate_revision(
                    response, critique, dimension_scores, dynamic_context, conversation_history
                )

            # Step 6: Calculate confidence based on score variance
            confidence = self._calculate_confidence(dimension_scores)

            return ValidationReport(
                overall_score=overall_score,
                dimension_scores=dimension_scores,
                violations=violations,
                critique=critique,
                suggested_revision=suggested_revision,
                confidence=confidence,
                passed=passed,
            )

        except Exception as e:
            logger.error(f"Validation failed: {e}")
            # Return a failed validation report rather than crashing
            return ValidationReport(
                overall_score=0.0,
                dimension_scores=dict.fromkeys(ConsistencyScore.DIMENSIONS, 0.0),
                violations=[
                    {
                        "dimension": "validation_system",
                        "severity": "critical",
                        "reason": f"Validation error: {str(e)}",
                    }
                ],
                critique=f"Validation system error: {str(e)}",
                passed=False,
                confidence=0.0,
            )

    async def validate_with_regeneration(
        self,
        initial_response: str,
        dynamic_context: DynamicContext,
        conversation_history: list[Message],
        max_attempts: int | None = None,
    ) -> tuple[str, list[ValidationReport]]:
        """Iterative validation with regeneration.

        Repeatedly validates and regenerates responses until:
        - Validation passes, OR
        - Maximum attempts reached

        Args:
            initial_response: The initial response to validate
            dynamic_context: Current dynamic context
            conversation_history: Recent conversation history
            max_attempts: Maximum regeneration attempts (default from config)

        Returns:
            Tuple of (final_response, list_of_validation_reports)
        """
        max_attempts = max_attempts or self.config.max_attempts
        current_response = initial_response
        reports: list[ValidationReport] = []

        for attempt in range(max_attempts):
            # Validate current response
            report = await self.validate(current_response, dynamic_context, conversation_history)
            reports.append(report)

            # If validation passed, return the response
            if report.passed:
                logger.info(f"Validation passed on attempt {attempt + 1}")
                return current_response, reports

            # If no revision suggestion was generated, we can't continue
            if not report.suggested_revision:
                logger.warning(f"No revision suggestion on attempt {attempt + 1}")
                break

            # Use the suggested revision for next iteration
            current_response = report.suggested_revision
            logger.info(f"Regenerated response for attempt {attempt + 2}")

        # Return the best response we have
        logger.warning(f"Validation failed after {len(reports)} attempts")
        return current_response, reports

    async def _score_dimensions(
        self,
        response: str,
        dynamic_context: DynamicContext,
        conversation_history: list[Message],
    ) -> dict[str, float]:
        """Score each consistency dimension.

        Args:
            response: The response to evaluate
            dynamic_context: Current dynamic context
            conversation_history: Recent conversation history

        Returns:
            Dictionary mapping dimension names to scores
        """
        scores: dict[str, float] = {}
        prompts = self._build_validation_prompts(response, dynamic_context, conversation_history)

        for dim_name in ConsistencyScore.DIMENSIONS:
            try:
                score = await self._evaluate_dimension(dim_name, prompts[dim_name])
                scores[dim_name] = score
            except Exception as e:
                logger.error(f"Failed to score dimension {dim_name}: {e}")
                scores[dim_name] = 0.0

        return scores

    async def _evaluate_dimension(self, dim_name: str, prompt: str) -> float:
        """Evaluate a single dimension using LLM.

        Args:
            dim_name: Name of the dimension to evaluate
            prompt: The evaluation prompt

        Returns:
            Score between 0.0 and 1.0
        """
        messages = [
            {
                "role": "system",
                "content": "You are an expert evaluator of character consistency. Always respond with valid JSON.",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            llm_response = await self.llm_client.chat(
                messages,
                temperature=self.config.temperature_scoring,
                max_tokens=500,
            )

            # Parse JSON response
            content = llm_response.content.strip()
            # Handle markdown code blocks
            if content.startswith("```"):
                lines = content.split("\n")
                # Remove first and last lines (```json and ```)
                content = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

            result = json.loads(content)
            score = float(result.get("score", 0.0))

            # Ensure score is within bounds
            return max(0.0, min(1.0, score))

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse dimension score JSON for {dim_name}: {e}")
            return 0.0
        except Exception as e:
            logger.error(f"Error evaluating dimension {dim_name}: {e}")
            return 0.0

    async def _generate_critique(
        self,
        response: str,
        scores: dict[str, float],
        dynamic_context: DynamicContext,
        violations: list[dict[str, Any]],
    ) -> str:
        """Generate detailed critique using chain-of-thought reasoning.

        Args:
            response: The response being critiqued
            scores: Dimension scores
            dynamic_context: Current dynamic context
            violations: List of validation violations

        Returns:
            Detailed critique text
        """
        # Build validation scores text
        scores_text = []
        for dim_name, score in scores.items():
            threshold = ConsistencyScore.DIMENSIONS[dim_name]["threshold"]
            status = "✓ PASS" if score >= threshold else "✗ FAIL"
            scores_text.append(f"- {dim_name}: {score:.3f} (threshold: {threshold}) {status}")

        # Build violations text
        violations_text = []
        for v in violations:
            violations_text.append(
                f"- [{v.get('severity', 'unknown').upper()}] {v.get('dimension', 'unknown')}: {v.get('reason', '')}"
            )

        prompt = VALIDATION_PROMPTS["self_critique"].format(
            character_name=self.core_identity.name,
            core_values=(
                ", ".join(self.core_identity.values.values)
                if self.core_identity.values.values
                else "None defined"
            ),
            backstory=(
                self.core_identity.backstory[:500]
                if self.core_identity.backstory
                else "Not specified"
            ),
            response=response,
            validation_scores="\n".join(scores_text),
            violations=(
                "\n".join(violations_text) if violations_text else "No specific violations recorded"
            ),
        )

        messages = [
            {
                "role": "system",
                "content": "You are an expert at critiquing character responses for consistency. Provide specific, actionable feedback.",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            llm_response = await self.llm_client.chat(
                messages,
                temperature=self.config.temperature_critique,
                max_tokens=800,
            )
            return llm_response.content.strip()
        except Exception as e:
            logger.error(f"Failed to generate critique: {e}")
            return f"Error generating critique: {str(e)}"

    async def _generate_revision(
        self,
        original: str,
        critique: str,
        scores: dict[str, float],
        dynamic_context: DynamicContext,
        conversation_history: list[Message],
    ) -> str:
        """Generate revised response addressing identified issues.

        Args:
            original: The original problematic response
            critique: The critique of issues
            scores: Dimension scores (to identify failed dimensions)
            dynamic_context: Current dynamic context
            conversation_history: Recent conversation history

        Returns:
            Revised response text
        """
        # Identify failed dimensions
        failed_dims = []
        for dim_name, score in scores.items():
            threshold = ConsistencyScore.DIMENSIONS[dim_name]["threshold"]
            if score < threshold:
                failed_dims.append(f"- {dim_name}: {score:.3f} < {threshold}")

        # Format conversation history
        history_text = []
        for msg in conversation_history[-5:]:  # Last 5 messages
            history_text.append(f"{msg.role}: {msg.content}")

        prompt = VALIDATION_PROMPTS["revision"].format(
            character_name=self.core_identity.name,
            core_values=(
                ", ".join(self.core_identity.values.values)
                if self.core_identity.values.values
                else "None defined"
            ),
            must_always=(
                ", ".join(self.core_identity.behavioral_matrix.must_always)
                if self.core_identity.behavioral_matrix.must_always
                else "None"
            ),
            must_never=(
                ", ".join(self.core_identity.behavioral_matrix.must_never)
                if self.core_identity.behavioral_matrix.must_never
                else "None"
            ),
            backstory=(
                self.core_identity.backstory[:500]
                if self.core_identity.backstory
                else "Not specified"
            ),
            original_response=original,
            critique=critique,
            failed_dimensions="\n".join(failed_dims) if failed_dims else "None",
            emotional_state=dynamic_context.emotional.primary_emotion,
            user_intent=dynamic_context.user_intent,
            conversation_history="\n".join(history_text) if history_text else "No prior context",
        )

        messages = [
            {
                "role": "system",
                "content": "You are an expert at revising character responses to improve consistency. Maintain the character's voice while fixing issues.",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            llm_response = await self.llm_client.chat(
                messages,
                temperature=self.config.temperature_revision,
                max_tokens=1000,
            )
            return llm_response.content.strip()
        except Exception as e:
            logger.error(f"Failed to generate revision: {e}")
            return original  # Return original if revision fails

    def _build_validation_prompts(
        self,
        response: str,
        dynamic_context: DynamicContext,
        conversation_history: list[Message],
    ) -> dict[str, str]:
        """Build LLM prompts for each validation dimension.

        Args:
            response: The response to evaluate
            dynamic_context: Current dynamic context
            conversation_history: Recent conversation history

        Returns:
            Dictionary mapping dimension names to formatted prompts
        """
        # Format conversation history
        history_text = []
        for msg in conversation_history[-5:]:  # Last 5 messages
            history_text.append(f"{msg.role}: {msg.content}")

        prompts = {}

        # Value alignment prompt
        prompts["value_alignment"] = VALIDATION_PROMPTS["value_alignment"].format(
            character_name=self.core_identity.name,
            core_values=(
                ", ".join(self.core_identity.values.values)
                if self.core_identity.values.values
                else "None defined"
            ),
            must_always=(
                ", ".join(self.core_identity.behavioral_matrix.must_always)
                if self.core_identity.behavioral_matrix.must_always
                else "None"
            ),
            must_never=(
                ", ".join(self.core_identity.behavioral_matrix.must_never)
                if self.core_identity.behavioral_matrix.must_never
                else "None"
            ),
            response=response,
            emotional_state=dynamic_context.emotional.primary_emotion,
            user_intent=dynamic_context.user_intent,
        )

        # Personality consistency prompt
        prompts["personality_consistency"] = VALIDATION_PROMPTS["personality_consistency"].format(
            character_name=self.core_identity.name,
            backstory=(
                self.core_identity.backstory[:500]
                if self.core_identity.backstory
                else "Not specified"
            ),
            traits=", ".join(
                [f"{k}={v}" for k, v in self.core_identity.values.model_dump().items() if v]
            ),
            response=response,
            emotional_state=dynamic_context.emotional.primary_emotion,
            relationship_stage=dynamic_context.social.current_stage,
        )

        # Historical coherence prompt
        prompts["historical_coherence"] = VALIDATION_PROMPTS["historical_coherence"].format(
            character_name=self.core_identity.name,
            conversation_history=(
                "\n".join(history_text) if history_text else "No prior conversation"
            ),
            response=response,
        )

        # Emotional appropriateness prompt
        prompts["emotional_appropriateness"] = VALIDATION_PROMPTS[
            "emotional_appropriateness"
        ].format(
            character_name=self.core_identity.name,
            emotional_state=f"{dynamic_context.emotional.primary_emotion} (valence={dynamic_context.emotional.valence:.2f}, arousal={dynamic_context.emotional.arousal:.2f})",
            user_intent=dynamic_context.user_intent,
            relationship_dynamics=f"intimacy={dynamic_context.social.intimacy:.2f}, trust={dynamic_context.social.trust:.2f}",
            response=response,
        )

        # Contextual awareness prompt
        prompts["contextual_awareness"] = VALIDATION_PROMPTS["contextual_awareness"].format(
            character_name=self.core_identity.name,
            topic=dynamic_context.topic,
            user_intent=dynamic_context.user_intent,
            conversation_turn=dynamic_context.conversation_turn,
            active_goals=(
                ", ".join(dynamic_context.cognitive.active_goals)
                if dynamic_context.cognitive.active_goals
                else "None"
            ),
            response=response,
        )

        return prompts

    def _calculate_confidence(self, scores: dict[str, float]) -> float:
        """Calculate confidence based on score variance and coverage.

        Args:
            scores: Dimension scores

        Returns:
            Confidence score between 0.0 and 1.0
        """
        if not scores:
            return 0.0

        # Check if all dimensions are present
        if len(scores) != len(ConsistencyScore.DIMENSIONS):
            return 0.5  # Partial confidence if dimensions missing

        # Calculate variance
        values = list(scores.values())
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)

        # High variance = lower confidence
        # Scale variance to 0-1 range (assuming max variance is 0.25)
        normalized_variance = min(variance / 0.25, 1.0)

        # Confidence is inverse of normalized variance
        confidence = 1.0 - (normalized_variance * 0.5)  # Scale impact

        return round(confidence, 3)

    def get_validation_stats(self) -> dict[str, Any]:
        """Get statistics about validation history.

        Returns:
            Dictionary with validation statistics
        """
        if not self.validation_history:
            return {
                "total_validations": 0,
                "pass_rate": 0.0,
                "average_score": 0.0,
            }

        total = len(self.validation_history)
        passed = sum(1 for v in self.validation_history if v.overall_valid)
        avg_score = sum(v.overall_score for v in self.validation_history) / total

        return {
            "total_validations": total,
            "pass_rate": passed / total,
            "average_score": round(avg_score, 3),
        }


# ============================================================================
# Exceptions
# ============================================================================


class ValidationError(PersonaAgentError):
    """Exception raised when validation fails catastrophically."""

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message, code="VALIDATION_ERROR", details=details)


# ============================================================================
# Exports
# ============================================================================


__all__ = [
    "ConsistencyScore",
    "ConsistencyValidator",
    "ValidationConfig",
    "ValidationReport",
    "Message",
    "ValidationError",
    "VALIDATION_PROMPTS",
]
