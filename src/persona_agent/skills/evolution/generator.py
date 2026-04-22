"""Evolution generator for creating improved skill code.

This module provides the EvolutionGenerator class which uses LLM
to generate improved skill code based on execution feedback.
"""

from __future__ import annotations

import inspect
import logging
import re
from datetime import UTC
from typing import TYPE_CHECKING, Protocol

from persona_agent.skills.evolution.exceptions import GenerationError, InvalidEvolutionModeError
from persona_agent.skills.evolution.models import EvolutionMode, EvolutionProposal, SkillMetrics

if TYPE_CHECKING:
    from persona_agent.skills.base import BaseSkill
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


class EvolutionGenerator:
    """Generate evolved skill code using LLM.

    This class creates improved versions of skills by:
    - Analyzing error patterns (FIX mode)
    - Optimizing successful patterns (DERIVED mode)
    - Learning from examples (CAPTURED mode)

    Example:
        generator = EvolutionGenerator(llm_client)
        proposal = await generator.generate(
            skill_name="weather_skill",
            skill_class=WeatherSkill,
            metrics=metrics,
            mode=EvolutionMode.FIX,
        )
    """

    FIX_PROMPT_TEMPLATE = """You are a skilled Python developer tasked with fixing bugs in an AI agent skill.

Original Skill Code:
```python
{original_code}
```

Performance Metrics:
- Total executions: {total_executions}
- Success rate: {success_rate:.1%}
- Recent errors:
{error_list}

Instructions:
1. Analyze the errors and identify the root cause
2. Fix the bugs while maintaining the skill's original purpose
3. Keep the same class name and interface
4. Add error handling where appropriate
5. Include comments explaining what was fixed

Provide the corrected Python code. Only output the code, no explanation."""

    DERIVED_PROMPT_TEMPLATE = """You are a skilled Python developer tasked with optimizing an AI agent skill.

Original Skill Code:
```python
{original_code}
```

Performance Metrics:
- Total executions: {total_executions}
- Success rate: {success_rate:.1%}
- Average execution time: {avg_time_ms:.0f}ms

Successful Execution Patterns:
{success_patterns}

Instructions:
1. Create an optimized version of this skill
2. Improve efficiency and reliability
3. Maintain the same interface (can_handle, execute methods)
4. Add "V2" suffix to the class name
5. Include docstring explaining improvements

Provide the optimized Python code. Only output the code, no explanation."""

    CAPTURED_PROMPT_TEMPLATE = """You are a skilled Python developer creating a new AI agent skill.

Skill Name: {skill_name}
Purpose: {purpose}

Example Interactions:
{examples}

Instructions:
1. Create a complete skill class inheriting from BaseSkill
2. Implement can_handle() to detect when this skill should trigger
3. Implement execute() to perform the skill's function
4. Include proper error handling
5. Add docstring and type hints

Provide the complete Python code for the new skill."""

    def __init__(self, llm_client: LLMClientProtocol | None = None) -> None:
        """Initialize the generator.

        Args:
            llm_client: LLM client for code generation
        """
        self.llm_client = llm_client

    async def generate(
        self,
        skill_name: str,
        skill_class: type[BaseSkill],
        metrics: SkillMetrics,
        mode: EvolutionMode,
        *,
        purpose: str | None = None,
        examples: list[dict] | None = None,
    ) -> EvolutionProposal:
        """Generate an evolution proposal.

        Args:
            skill_name: Name of the skill
            skill_class: The skill class to evolve
            metrics: Performance metrics
            mode: Evolution mode
            purpose: For CAPTURED mode, description of purpose
            examples: For CAPTURED mode, example interactions

        Returns:
            EvolutionProposal with generated code

        Raises:
            GenerationError: If generation fails
            InvalidEvolutionModeError: If mode is invalid
        """
        if not self.llm_client:
            raise GenerationError(
                "No LLM client available",
                skill_name=skill_name,
                mode=mode.value,
            )

        # Get original code
        try:
            original_code = inspect.getsource(skill_class)
        except (TypeError, OSError) as e:
            raise GenerationError(
                f"Failed to get source code: {e}",
                skill_name=skill_name,
                mode=mode.value,
            ) from e

        # Build prompt based on mode
        prompt = self._build_prompt(
            mode=mode,
            skill_name=skill_name,
            original_code=original_code,
            metrics=metrics,
            purpose=purpose,
            examples=examples,
        )

        try:
            # Generate code
            response = await self.llm_client.chat(
                messages=[
                    {"role": "system", "content": "You are an expert Python developer."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )

            proposed_code = self._extract_code(response.content)
            reasoning = self._extract_reasoning(response.content)

            # Create proposal
            from datetime import datetime

            proposal = EvolutionProposal(
                id=f"{skill_name}_{mode.value}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}",
                skill_name=skill_name,
                mode=mode,
                original_code=original_code,
                proposed_code=proposed_code,
                reasoning=reasoning,
                created_at=datetime.now(UTC),
                metrics_at_creation=metrics.to_dict(),
            )

            logger.info(f"Generated {mode.value} proposal for {skill_name}")
            return proposal

        except Exception as e:
            logger.error(f"Failed to generate evolution: {e}")
            raise GenerationError(
                f"Generation failed: {e}",
                skill_name=skill_name,
                mode=mode.value,
            ) from e

    def _build_prompt(
        self,
        mode: EvolutionMode,
        skill_name: str,
        original_code: str,
        metrics: SkillMetrics,
        purpose: str | None = None,
        examples: list[dict] | None = None,
    ) -> str:
        """Build the generation prompt."""
        if mode == EvolutionMode.FIX:
            return self.FIX_PROMPT_TEMPLATE.format(
                original_code=original_code,
                total_executions=metrics.total_executions,
                success_rate=metrics.success_rate,
                error_list=self._format_errors(metrics),
            )

        elif mode == EvolutionMode.DERIVED:
            return self.DERIVED_PROMPT_TEMPLATE.format(
                original_code=original_code,
                total_executions=metrics.total_executions,
                success_rate=metrics.success_rate,
                avg_time_ms=metrics.average_execution_time_ms,
                success_patterns=self._format_success_patterns(metrics),
            )

        elif mode == EvolutionMode.CAPTURED:
            return self.CAPTURED_PROMPT_TEMPLATE.format(
                skill_name=skill_name,
                purpose=purpose or "Handle user requests",
                examples=self._format_examples(examples or []),
            )

        else:
            raise InvalidEvolutionModeError(mode.value)

    def _format_errors(self, metrics: SkillMetrics) -> str:
        """Format recent errors for prompt."""
        errors = metrics.get_recent_errors(count=5)
        if not errors:
            return "  - No specific error messages recorded"

        lines = []
        for i, error in enumerate(errors, 1):
            lines.append(f"  {i}. {error[:150]}")

        return "\n".join(lines)

    def _format_success_patterns(self, metrics: SkillMetrics) -> str:
        """Format successful execution patterns."""
        # Get successful executions
        successes = [ex for ex in metrics.execution_history if ex.success][-5:]

        if not successes:
            return "  - No successful execution patterns recorded"

        lines = []
        for ex in successes:
            lines.append(f"  - Input: {ex.input_summary[:100]}")

        return "\n".join(lines)

    def _format_examples(self, examples: list[dict]) -> str:
        """Format example interactions for prompt."""
        if not examples:
            return "  - No examples provided"

        lines = []
        for i, ex in enumerate(examples, 1):
            user_input = ex.get("input", "")
            response = ex.get("response", "")
            lines.append(f"  {i}. User: {user_input[:100]}")
            lines.append(f"     Response: {response[:100]}")

        return "\n".join(lines)

    def _extract_code(self, content: str) -> str:
        """Extract code from LLM response."""
        # Try to extract from markdown code block
        patterns = [
            r"```python\s*(.*?)\s*```",
            r"```\s*(.*?)\s*```",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                return match.group(1).strip()

        # If no code block, return entire content
        return content.strip()

    def _extract_reasoning(self, content: str) -> str:
        """Extract reasoning from LLM response."""
        # Look for comments at the top of the code
        lines = content.split("\n")
        comments = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""'):
                comments.append(stripped)
            elif stripped and not stripped.startswith("class"):
                continue
            else:
                break

        return " ".join(comments) if comments else "Generated by LLM"


__all__ = ["EvolutionGenerator"]
