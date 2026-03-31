"""Persona manager for persona-agent.

Manages character profiles and coordinates between configuration,
mood engine, and linguistic style.
"""

import logging
from pathlib import Path

from persona_agent.config.loader import ConfigLoader
from persona_agent.config.schemas.character import CharacterProfile
from persona_agent.config.schemas.linguistic import LinguisticStyle
from persona_agent.core.mood_engine import MoodEngine

logger = logging.getLogger(__name__)


class PersonaManager:
    """Manages character personas and their configurations.

    Coordinates between:
    - Character profile (who the character is)
    - Mood engine (how they feel)
    - Linguistic style (how they speak)
    """

    def __init__(
        self,
        config_loader: ConfigLoader | None = None,
        character_name: str | None = None,
    ):
        """Initialize persona manager.

        Args:
            config_loader: ConfigLoader instance
            character_name: Name of character to load
        """
        self.config_loader = config_loader or ConfigLoader()
        self._current_character: CharacterProfile | None = None
        self._mood_engine: MoodEngine | None = None
        self._linguistic_style: LinguisticStyle | None = None

        if character_name:
            self.load_character(character_name)

    def load_character(self, name: str) -> CharacterProfile:
        """Load a character by name.

        Args:
            name: Character name

        Returns:
            Loaded character profile
        """
        # Load character profile
        self._current_character = self.config_loader.load_character(name)
        logger.info(f"Loaded character: {self._current_character.name}")

        # Load associated mood config
        if self._current_character.mood_config:
            mood_path = Path(self._current_character.mood_config)
            if not mood_path.is_absolute():
                # Resolve relative to config dir
                mood_path = self.config_loader.config_dir / mood_path

            if mood_path.exists():
                self._mood_engine = MoodEngine.from_config(mood_path)
                logger.debug(f"Loaded mood config: {mood_path}")
            else:
                logger.warning(f"Mood config not found: {mood_path}")
                self._mood_engine = MoodEngine()
        else:
            self._mood_engine = MoodEngine()

        # Load associated linguistic style
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

        return self._current_character

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

        Returns:
            System prompt string
        """
        if not self._current_character:
            raise RuntimeError("No character loaded")

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
