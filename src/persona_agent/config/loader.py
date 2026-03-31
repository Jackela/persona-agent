"""Configuration loader for persona-agent."""

import logging
from pathlib import Path

from persona_agent.config.schemas.character import CharacterProfile
from persona_agent.config.schemas.linguistic import LinguisticStyle
from persona_agent.config.schemas.mood import MoodDefinition

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Load and manage persona-agent configurations.

    Supports loading from multiple sources with priority:
    1. Environment variables
    2. Project local config (./config/)
    3. User global config (~/.config/persona-agent/)
    4. Default configs (package defaults)
    """

    def __init__(self, config_dir: Path | None = None):
        """Initialize the config loader.

        Args:
            config_dir: Optional specific config directory to use
        """
        self.config_dir = config_dir or self._find_config_dir()
        self._character_cache: dict[str, CharacterProfile] = {}
        self._mood_cache: dict[str, list[MoodDefinition]] = {}
        self._style_cache: dict[str, LinguisticStyle] = {}

    def _find_config_dir(self) -> Path:
        """Find the appropriate config directory."""
        # Check for local config first
        local_config = Path.cwd() / "config"
        if local_config.exists():
            return local_config

        # Fall back to user config
        user_config = Path.home() / ".config" / "persona-agent"
        if user_config.exists():
            return user_config

        # Create user config if neither exists
        user_config.mkdir(parents=True, exist_ok=True)
        return user_config

    def load_character(self, name: str) -> CharacterProfile:
        """Load a character profile by name.

        Args:
            name: Character name (filename without extension)

        Returns:
            CharacterProfile instance

        Raises:
            FileNotFoundError: If the character config doesn't exist
        """
        if name in self._character_cache:
            return self._character_cache[name]

        char_path = self.config_dir / "characters" / f"{name}.yaml"
        if not char_path.exists():
            # Try alternative extensions
            char_path = self.config_dir / "characters" / f"{name}.yml"

        if not char_path.exists():
            raise FileNotFoundError(
                f"Character '{name}' not found in {self.config_dir / 'characters'}"
            )

        profile = CharacterProfile.from_yaml(char_path)
        self._character_cache[name] = profile
        logger.debug(f"Loaded character profile: {name}")
        return profile

    def load_linguistic_style(self, name: str) -> LinguisticStyle:
        """Load a linguistic style by name.

        Args:
            name: Style name (filename without extension)

        Returns:
            LinguisticStyle instance

        Raises:
            FileNotFoundError: If the style config doesn't exist
        """
        if name in self._style_cache:
            return self._style_cache[name]

        style_path = self.config_dir / "linguistic_styles" / f"{name}.json"

        if not style_path.exists():
            raise FileNotFoundError(
                f"Linguistic style '{name}' not found in {self.config_dir / 'linguistic_styles'}"
            )

        style = LinguisticStyle.from_json(style_path)
        self._style_cache[name] = style
        logger.debug(f"Loaded linguistic style: {name}")
        return style

    def load_mood_states(self, name: str = "default") -> list[MoodDefinition]:
        """Load mood state definitions.

        Args:
            name: Mood config name (filename without extension)

        Returns:
            List of MoodDefinition instances

        Raises:
            FileNotFoundError: If the mood config doesn't exist
        """
        if name in self._mood_cache:
            return self._mood_cache[name]

        mood_path = self.config_dir / "mood_states" / f"{name}.md"

        if not mood_path.exists():
            raise FileNotFoundError(
                f"Mood states '{name}' not found in {self.config_dir / 'mood_states'}"
            )

        moods = MoodDefinition.from_markdown(mood_path)
        self._mood_cache[name] = moods
        logger.debug(f"Loaded {len(moods)} mood definitions from: {name}")
        return moods

    def load_system_goal(self) -> str:
        """Load the system goal/prompt.

        Returns:
            System goal text

        Raises:
            FileNotFoundError: If the system goal file doesn't exist
        """
        goal_path = self.config_dir / "system_goal.txt"

        if not goal_path.exists():
            raise FileNotFoundError(f"System goal not found: {goal_path}")

        with open(goal_path, encoding="utf-8") as f:
            content = f.read()

        # Remove line number prefixes if present (from our format)
        lines = []
        for line in content.split("\n"):
            # Remove pattern like "1#QQ|" from beginning of line
            import re

            cleaned = re.sub(r"^\d+#[A-Z]+\|", "", line)
            lines.append(cleaned)

        return "\n".join(lines)

    def list_characters(self) -> list[str]:
        """List available character profiles.

        Returns:
            List of character names
        """
        chars_dir = self.config_dir / "characters"
        if not chars_dir.exists():
            return []

        characters = []
        for ext in [".yaml", ".yml"]:
            for file in chars_dir.glob(f"*{ext}"):
                characters.append(file.stem)

        return sorted(characters)

    def list_linguistic_styles(self) -> list[str]:
        """List available linguistic styles.

        Returns:
            List of style names
        """
        styles_dir = self.config_dir / "linguistic_styles"
        if not styles_dir.exists():
            return []

        return sorted([f.stem for f in styles_dir.glob("*.json")])

    def list_mood_states(self) -> list[str]:
        """List available mood state configs.

        Returns:
            List of mood config names
        """
        moods_dir = self.config_dir / "mood_states"
        if not moods_dir.exists():
            return []

        return sorted([f.stem for f in moods_dir.glob("*.md")])

    def clear_cache(self) -> None:
        """Clear all configuration caches."""
        self._character_cache.clear()
        self._mood_cache.clear()
        self._style_cache.clear()
        logger.debug("Configuration cache cleared")
