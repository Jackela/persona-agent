"""Persona manager for persona-agent (refactored with new architecture).

This module provides an enhanced PersonaManager that integrates with the new
architecture components, particularly the LayeredPromptEngine for building
three-layer prompts with RoleRAG integration.
"""

from __future__ import annotations

import logging
from pathlib import Path

from persona_agent.config.loader import ConfigLoader
from persona_agent.config.schemas.character import CharacterProfile
from persona_agent.config.schemas.linguistic import LinguisticStyle
from persona_agent.core.mood_engine import MoodEngine
from persona_agent.core.prompt_engine import LayeredPromptEngine
from persona_agent.core.schemas import (
    BehavioralMatrix,
    CoreIdentity,
    CoreValues,
    KnowledgeBoundary,
)
from persona_agent.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


class NewArchitecturePersonaManager:
    """Enhanced persona manager with new architecture integration.

    This manager extends the original PersonaManager with:
    - LayeredPromptEngine integration for three-layer prompts
    - RoleRAG knowledge boundary management
    - CoreIdentity construction from character profiles
    - Backward compatibility with existing code

    The manager can operate in two modes:
    1. Legacy mode: Uses original MoodEngine and prompt building
    2. New architecture mode: Uses LayeredPromptEngine with RoleRAG
    """

    def __init__(
        self,
        config_loader: ConfigLoader | None = None,
        character_name: str | None = None,
        llm_client: LLMClient | None = None,
        use_new_architecture: bool = True,
    ):
        """Initialize the enhanced persona manager.

        Args:
            config_loader: ConfigLoader instance
            character_name: Name of character to load
            llm_client: LLM client for RoleRAG operations
            use_new_architecture: Whether to use new architecture features
        """
        self.config_loader = config_loader or ConfigLoader()
        self.llm_client = llm_client
        self.use_new_architecture = use_new_architecture

        # Legacy components
        self._current_character: CharacterProfile | None = None
        self._mood_engine: MoodEngine | None = None
        self._linguistic_style: LinguisticStyle | None = None

        # New architecture components
        self._core_identity: CoreIdentity | None = None
        self._knowledge_boundary: KnowledgeBoundary | None = None
        self._prompt_engine: LayeredPromptEngine | None = None

        if character_name:
            self.load_character(character_name)

    def load_character(self, name: str) -> CharacterProfile:
        """Load a character by name.

        This method loads the character and initializes both legacy
        and new architecture components.

        Args:
            name: Character name

        Returns:
            Loaded character profile
        """
        # Load character profile
        self._current_character = self.config_loader.load_character(name)
        logger.info(f"Loaded character: {self._current_character.name}")

        # Load associated mood config (legacy)
        self._load_mood_engine()

        # Load associated linguistic style (legacy)
        self._load_linguistic_style()

        # Initialize new architecture components
        if self.use_new_architecture:
            self._init_new_architecture_components()

        return self._current_character

    def _load_mood_engine(self) -> None:
        """Load mood engine configuration."""
        if not self._current_character:
            return

        if self._current_character.mood_config:
            mood_path = Path(self._current_character.mood_config)
            if not mood_path.is_absolute():
                mood_path = self.config_loader.config_dir / mood_path

            if mood_path.exists():
                self._mood_engine = MoodEngine.from_config(mood_path)
                logger.debug(f"Loaded mood config: {mood_path}")
            else:
                logger.warning(f"Mood config not found: {mood_path}")
                self._mood_engine = MoodEngine()
        else:
            self._mood_engine = MoodEngine()

    def _load_linguistic_style(self) -> None:
        """Load linguistic style configuration."""
        if not self._current_character:
            return

        if self._current_character.linguistic_style:
            style_path = Path(self._current_character.linguistic_style)
            if not style_path.is_absolute():
                style_path = self.config_loader.config_dir / style_path

            if style_path.exists():
                self._linguistic_style = LinguisticStyle.from_json(style_path)
                logger.debug(f"Loaded linguistic style: {style_path}")
            else:
                logger.warning(f"Linguistic style not found: {style_path}")
                self._linguistic_style = LinguisticStyle()
        else:
            self._linguistic_style = LinguisticStyle()

    def _init_new_architecture_components(self) -> None:
        """Initialize new architecture components from character profile."""
        if not self._current_character:
            return

        # Build CoreIdentity from character profile
        self._core_identity = self._build_core_identity()

        # Build KnowledgeBoundary from character profile
        self._knowledge_boundary = self._build_knowledge_boundary()

        # Initialize LayeredPromptEngine
        if self.llm_client:
            self._prompt_engine = LayeredPromptEngine(
                core_identity=self._core_identity,
                knowledge_boundary=self._knowledge_boundary,
                llm_client=self.llm_client,
            )
            logger.debug("Initialized LayeredPromptEngine")

    def _build_core_identity(self) -> CoreIdentity:
        """Build CoreIdentity from character profile.

        Returns:
            CoreIdentity for the current character
        """
        char = self._current_character
        assert char is not None

        # Extract values from character
        values = CoreValues(
            values=char.core_values if hasattr(char, "core_values") else [],
            fears=char.fears if hasattr(char, "fears") else [],
            desires=char.desires if hasattr(char, "desires") else [],
            boundaries=char.boundaries if hasattr(char, "boundaries") else [],
        )

        # Extract behavioral matrix
        behavioral = BehavioralMatrix(
            must_always=char.must_always if hasattr(char, "must_always") else [],
            must_never=char.forbidden_topics if hasattr(char, "forbidden_topics") else [],
            should_avoid=char.should_avoid if hasattr(char, "should_avoid") else [],
        )

        return CoreIdentity(
            name=char.name,
            version=char.version if hasattr(char, "version") else "1.0.0",
            backstory=char.backstory or "",
            values=values,
            behavioral_matrix=behavioral,
        )

    def _build_knowledge_boundary(self) -> KnowledgeBoundary:
        """Build KnowledgeBoundary from character profile.

        Returns:
            KnowledgeBoundary for the current character
        """
        char = self._current_character
        assert char is not None

        return KnowledgeBoundary(
            known_domains=char.knowledge_domains if hasattr(char, "knowledge_domains") else [],
            known_entities=char.known_entities if hasattr(char, "known_entities") else [],
            unknown_domains=char.unknown_domains if hasattr(char, "unknown_domains") else [],
            confidence=char.knowledge_confidence if hasattr(char, "knowledge_confidence") else 0.8,
        )

    def get_character(self) -> CharacterProfile | None:
        """Get current character profile.

        Returns:
            Current character or None
        """
        return self._current_character

    def get_mood_engine(self) -> MoodEngine | None:
        """Get mood engine.

        Returns:
            MoodEngine instance
        """
        return self._mood_engine

    def get_linguistic_style(self) -> LinguisticStyle | None:
        """Get linguistic style.

        Returns:
            LinguisticStyle instance
        """
        return self._linguistic_style

    def get_core_identity(self) -> CoreIdentity | None:
        """Get core identity (new architecture).

        Returns:
            CoreIdentity or None if not using new architecture
        """
        return self._core_identity

    def get_knowledge_boundary(self) -> KnowledgeBoundary | None:
        """Get knowledge boundary (new architecture).

        Returns:
            KnowledgeBoundary or None if not using new architecture
        """
        return self._knowledge_boundary

    def get_prompt_engine(self) -> LayeredPromptEngine | None:
        """Get layered prompt engine (new architecture).

        Returns:
            LayeredPromptEngine or None
        """
        return self._prompt_engine

    def update_mood(self, trigger: str, context: dict | None = None) -> None:
        """Update character mood.

        Args:
            trigger: Mood trigger
            context: Additional context
        """
        if self._mood_engine:
            self._mood_engine.update(trigger, context)

    def build_system_prompt(self) -> str:
        """Build complete system prompt for current persona.

        This method uses the new LayeredPromptEngine when available,
        otherwise falls back to the legacy implementation.

        Returns:
            System prompt string
        """
        if not self._current_character:
            raise RuntimeError("No character loaded")

        # Use new architecture if available
        if self.use_new_architecture and self._prompt_engine:
            return self._build_system_prompt_new_architecture()

        # Fall back to legacy implementation
        return self._build_system_prompt_legacy()

    def _build_system_prompt_legacy(self) -> str:
        """Build system prompt using legacy implementation."""
        components = []

        # Add character context
        components.append(self._current_character.to_prompt_context())

        # Add mood modifier
        if self._mood_engine:
            mood_modifier = self._mood_engine.get_prompt_modifier()
            if mood_modifier:
                components.append(mood_modifier)

        # Add linguistic guidelines
        if self._linguistic_style:
            guidelines = self._build_linguistic_guidelines()
            if guidelines:
                components.append(guidelines)

        return "\n\n".join(components)

    def _build_system_prompt_new_architecture(self) -> str:
        """Build system prompt using new architecture.

        This creates a three-layer prompt using the LayeredPromptEngine.
        Note: This is a simplified version without dynamic context.
        For full three-layer prompts, use build_layered_prompt().

        Returns:
            System prompt string
        """
        if not self._prompt_engine:
            return self._build_system_prompt_legacy()

        # Build a basic layered prompt without dynamic context
        # This returns the static Layer 1 (Core Identity) + basic Layer 3
        from persona_agent.core.schemas import DynamicContext

        dynamic_context = DynamicContext()

        # Add mood information to dynamic context if available
        if self._mood_engine:
            # Convert legacy mood to emotional state
            from persona_agent.core.schemas import EmotionalState

            mood_name = self._mood_engine.current_state.name

            # Simple mood mapping
            mood_to_emotion = {
                "happy": EmotionalState(valence=0.7, arousal=0.6, primary_emotion="happy"),
                "sad": EmotionalState(valence=-0.6, arousal=0.3, primary_emotion="sad"),
                "angry": EmotionalState(valence=-0.7, arousal=0.8, primary_emotion="angry"),
                "calm": EmotionalState(valence=0.3, arousal=0.2, primary_emotion="calm"),
            }
            dynamic_context.emotional = mood_to_emotion.get(mood_name, EmotionalState())

        # Use synchronous version to get prompt
        return self._prompt_engine.get_system_prompt(
            user_input="",
            dynamic_context=dynamic_context,
        )

    async def build_layered_prompt(self, user_input: str, context: dict | None = None) -> str:
        """Build a complete three-layer prompt with RoleRAG.

        This is the advanced method that uses all three layers:
        - Layer 1: Core Identity (static)
        - Layer 2: Dynamic Context (emotional, social, cognitive)
        - Layer 3: Knowledge & Task (RoleRAG retrieval)

        Args:
            user_input: User's input for context
            context: Additional context dictionary

        Returns:
            Complete three-layer system prompt
        """
        if not self.use_new_architecture or not self._prompt_engine:
            # Fall back to legacy
            return self.build_system_prompt()

        from persona_agent.core.schemas import DynamicContext, TaskContext

        # Build dynamic context from inputs
        dynamic_context = DynamicContext()

        # Add mood information
        if self._mood_engine:
            from persona_agent.core.schemas import EmotionalState

            mood_name = self._mood_engine.current_state.name
            mood_to_emotion = {
                "happy": EmotionalState(valence=0.7, arousal=0.6, primary_emotion="happy"),
                "sad": EmotionalState(valence=-0.6, arousal=0.3, primary_emotion="sad"),
                "angry": EmotionalState(valence=-0.7, arousal=0.8, primary_emotion="angry"),
                "calm": EmotionalState(valence=0.3, arousal=0.2, primary_emotion="calm"),
            }
            dynamic_context.emotional = mood_to_emotion.get(mood_name, EmotionalState())

        # Build task context
        task_context = TaskContext(
            task_type="conversation",
            instructions=context.get("instructions", "") if context else "",
        )

        # Build layered prompt with RoleRAG
        layered_prompt = await self._prompt_engine.build_prompt(
            user_input=user_input,
            dynamic_context=dynamic_context,
            task_context=task_context,
        )

        return layered_prompt.to_system_prompt()

    def _build_linguistic_guidelines(self) -> str:
        """Build linguistic style guidelines.

        Returns:
            Guidelines string
        """
        if not self._linguistic_style:
            return ""

        lines = ["## 语言风格指南"]

        # Add nickname usage
        if self._linguistic_style.nicknames_for_user:
            lines.append(
                f"**可用称呼**: {', '.join(self._linguistic_style.nicknames_for_user[:5])}"
            )

        # Add verbal tic categories
        if self._mood_engine:
            tic_categories = self._mood_engine.get_verbal_tic_categories()
            if tic_categories:
                lines.append(f"**当前情绪口头禅**: {', '.join(tic_categories)}")

        # Add kaomoji guidance
        if self._mood_engine:
            kaomoji_cats = self._mood_engine.get_kaomoji_categories()
            if kaomoji_cats:
                lines.append(f"**推荐颜文字类别**: {', '.join(kaomoji_cats[:3])}")

        return "\n".join(lines)

    def list_available_characters(self) -> list[str]:
        """List available characters.

        Returns:
            List of character names
        """
        return self.config_loader.list_characters()

    def apply_linguistic_style(
        self,
        text: str,
        use_kaomoji: bool = True,
        use_nickname: bool = False,
    ) -> str:
        """Apply linguistic style to text.

        Args:
            text: Base text
            use_kaomoji: Whether to add kaomoji
            use_nickname: Whether to use nickname

        Returns:
            Styled text
        """
        if not self._linguistic_style or not self._mood_engine:
            return text

        mood = self._mood_engine.current_state.name
        return self._linguistic_style.apply_to_text(
            text,
            mood=mood,
            use_kaomoji=use_kaomoji,
            use_nickname=use_nickname,
        )


# Backward compatibility alias
PersonaManager = NewArchitecturePersonaManager

__all__ = ["NewArchitecturePersonaManager", "PersonaManager"]
