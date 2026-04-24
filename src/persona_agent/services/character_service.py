"""Character service for managing character configurations."""

from pathlib import Path
from typing import Self

import yaml

from persona_agent.config.loader import ConfigLoader
from persona_agent.config.schemas.character import CharacterProfile
from persona_agent.utils.exceptions import (
    AgentFileNotFoundError as PAFileNotFoundError,
)
from persona_agent.utils.exceptions import (
    ConfigurationError,
)


class CharacterServiceError(ConfigurationError):
    """Base exception for character service errors."""

    def __init__(self, message: str, character_name: str | None = None, **kwargs):
        super().__init__(
            message,
            **kwargs,
        )
        if character_name:
            self.details["character_name"] = character_name


class CharacterNotFoundError(CharacterServiceError):
    """Character not found error."""

    def __init__(self, character_name: str, **kwargs):
        super().__init__(
            f"Character '{character_name}' not found",
            character_name=character_name,
            **kwargs,
        )
        self.code = "CHARACTER_NOT_FOUND"


class CharacterLoadError(CharacterServiceError):
    """Error loading character configuration."""

    def __init__(self, character_name: str, reason: str, **kwargs):
        super().__init__(
            f"Failed to load character '{character_name}': {reason}",
            character_name=character_name,
            **kwargs,
        )
        self.code = "CHARACTER_LOAD_ERROR"
        self.details["reason"] = reason


class CharacterService:
    """Service for managing character configurations.

    This service wraps the ConfigLoader to provide a clean API for
    character management, handling errors gracefully and returning
    typed data structures.

    Attributes:
        _loader: Internal ConfigLoader instance

    Example:
        >>> service = CharacterService()
        >>> characters = service.list_characters()
        >>> character = service.get_character("default")
    """

    def __init__(self, config_dir: Path | None = None) -> None:
        """Initialize the character service.

        Args:
            config_dir: Optional path to configuration directory.
                       If not provided, uses default ConfigLoader behavior.
        """
        self._loader = ConfigLoader(config_dir)

    def list_characters(self) -> list[str]:
        """List all available character names.

        Returns:
            Sorted list of character names (without file extensions)

        Example:
            >>> service = CharacterService()
            >>> names = service.list_characters()
            >>> print(names)
            ['companion', 'default', 'pixel']
        """
        return self._loader.list_characters()

    def get_character(self, name: str) -> CharacterProfile:
        """Get a character profile by name.

        Args:
            name: Character name (filename without extension)

        Returns:
            CharacterProfile instance with full character data

        Raises:
            CharacterNotFoundError: If character doesn't exist
            CharacterLoadError: If character file is invalid

        Example:
            >>> service = CharacterService()
            >>> char = service.get_character("default")
            >>> print(char.name)
            '温柔助手'
        """
        try:
            return self._loader.load_character(name)
        except PAFileNotFoundError as e:
            raise CharacterNotFoundError(name) from e
        except (OSError, yaml.YAMLError) as e:
            raise CharacterLoadError(name, str(e)) from e

    def load_character(self, path: Path) -> CharacterProfile:
        """Load a character from a specific file path.

        This method allows loading character profiles from arbitrary
        file paths, not just the configured characters directory.

        Args:
            path: Path to the YAML character configuration file

        Returns:
            CharacterProfile instance with full character data

        Raises:
            CharacterNotFoundError: If file doesn't exist
            CharacterLoadError: If file is invalid or can't be parsed

        Example:
            >>> service = CharacterService()
            >>> char = service.load_character(Path("/path/to/custom.yaml"))
        """
        if not path.exists():
            raise CharacterNotFoundError(
                path.stem,
                file_path=str(path),
            )

        try:
            return CharacterProfile.from_yaml(path)
        except yaml.YAMLError as e:
            raise CharacterLoadError(
                path.stem,
                f"Invalid YAML: {e}",
                file_path=str(path),
            ) from e
        except Exception as e:
            raise CharacterLoadError(
                path.stem,
                str(e),
                file_path=str(path),
            ) from e

    def character_exists(self, name: str) -> bool:
        """Check if a character exists.

        Args:
            name: Character name to check

        Returns:
            True if character exists, False otherwise

        Example:
            >>> service = CharacterService()
            >>> if service.character_exists("default"):
            ...     print("Character exists")
        """
        return name in self._loader.list_characters()

    def clear_cache(self) -> None:
        """Clear the internal character cache.

        This forces reload of character configurations on next access.
        """
        self._loader.clear_cache()

    def _validate_character_name(self, name: str) -> None:
        """Validate that a character name is safe for use as a filename.

        Args:
            name: Character name to validate

        Raises:
            CharacterServiceError: If the character name is unsafe for filenames
        """
        unsafe_chars = {"/", "\\", "..", ":", "<", ">", "|", "*", "?", '"'}
        if any(ch in name for ch in unsafe_chars) or not name.strip():
            raise CharacterServiceError(
                f"Invalid character name: {name}",
                character_name=name,
            )

    def save_character(self, profile: CharacterProfile) -> Path:
        """Save a character profile to YAML.

        Args:
            profile: CharacterProfile to save

        Returns:
            Path where the character was saved
        """
        path = self._loader.config_dir / "characters" / f"{profile.name}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        profile.to_yaml(path)
        return path

    def create_character(self, profile: CharacterProfile) -> Path:
        """Create a new character profile.

        Saves to config/characters/{name}.yaml and validates
        filename safety to prevent path traversal.

        Args:
            profile: CharacterProfile to create

        Returns:
            Path where the character was saved

        Raises:
            CharacterServiceError: If the character name is unsafe for filenames
        """
        self._validate_character_name(profile.name)

        path = self._loader.config_dir / "characters" / f"{profile.name}.yaml"
        self.save_character(profile)
        self.clear_cache()
        return path

    def update_character(self, name: str, profile: CharacterProfile) -> Path:
        """Update an existing character profile.

        Args:
            name: Name of the character to update
            profile: Updated CharacterProfile

        Returns:
            Path where the character was saved
        """
        self._validate_character_name(name)

        path = self._loader.config_dir / "characters" / f"{name}.yaml"
        self.save_character(profile)
        self.clear_cache()
        return path

    @classmethod
    def with_config_dir(cls, config_dir: Path) -> Self:
        """Create a service with a specific config directory.

        Convenience factory method for creating a service instance
        with a specific configuration directory.

        Args:
            config_dir: Path to configuration directory

        Returns:
            New CharacterService instance

        Example:
            >>> service = CharacterService.with_config_dir(Path("/custom/config"))
        """
        return cls(config_dir)
