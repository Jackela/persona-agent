"""Configuration validation utilities."""

from pathlib import Path
from typing import Any

from persona_agent.config.schemas.character import CharacterProfile
from persona_agent.config.schemas.linguistic import LinguisticStyle
from persona_agent.config.schemas.mood import MoodDefinition


class ConfigValidator:
    """Validate configuration files and directories."""

    def __init__(self, config_dir: Path | str = "config"):
        """Initialize validator.

        Args:
            config_dir: Path to configuration directory
        """
        self.config_dir = Path(config_dir)
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate_all(self) -> bool:
        """Validate all configuration.

        Returns:
            True if valid, False otherwise
        """
        self.errors = []
        self.warnings = []

        # Validate structure
        self._validate_directory_structure()

        # Validate characters
        self._validate_characters()

        # Validate mood states
        self._validate_mood_states()

        # Validate linguistic styles
        self._validate_linguistic_styles()

        return len(self.errors) == 0

    def _validate_directory_structure(self) -> None:
        """Validate that required directories exist."""
        required_dirs = ["characters", "mood_states", "linguistic_styles"]

        for dir_name in required_dirs:
            dir_path = self.config_dir / dir_name
            if not dir_path.exists():
                self.errors.append(f"Required directory missing: {dir_path}")

    def _validate_characters(self) -> None:
        """Validate character configurations."""
        chars_dir = self.config_dir / "characters"
        if not chars_dir.exists():
            return

        for char_file in chars_dir.glob("*.yaml"):
            try:
                profile = CharacterProfile.from_yaml(char_file)

                # Check required fields
                if not profile.name:
                    self.errors.append(f"Character {char_file.stem}: missing name")

                if not profile.relationship:
                    self.warnings.append(f"Character {char_file.stem}: missing relationship")

            except (ValueError, TypeError, KeyError, RuntimeError) as e:
                error_msg = str(e)
                if "name" in error_msg.lower() and (
                    "required" in error_msg.lower() or "missing" in error_msg.lower()
                ):
                    self.errors.append(f"Character {char_file.stem}: missing name")
                else:
                    self.errors.append(f"Character {char_file.stem}: {e}")

        # Also check .yml files
        for char_file in chars_dir.glob("*.yml"):
            try:
                profile = CharacterProfile.from_yaml(char_file)

                if not profile.name:
                    self.errors.append(f"Character {char_file.stem}: missing name")

                if not profile.relationship:
                    self.warnings.append(f"Character {char_file.stem}: missing relationship")

            except (ValueError, TypeError, KeyError, RuntimeError) as e:
                error_msg = str(e)
                if "name" in error_msg.lower() and (
                    "required" in error_msg.lower() or "missing" in error_msg.lower()
                ):
                    self.errors.append(f"Character {char_file.stem}: missing name")
                else:
                    self.errors.append(f"Character {char_file.stem}: {e}")

    def _validate_mood_states(self) -> None:
        """Validate mood state configurations."""
        moods_dir = self.config_dir / "mood_states"
        if not moods_dir.exists():
            return

        for mood_file in moods_dir.glob("*.md"):
            try:
                moods = MoodDefinition.from_markdown(mood_file)

                if not moods:
                    self.warnings.append(f"Mood file {mood_file.name}: no mood definitions found")

                # Check for duplicate mood names
                names = [m.name for m in moods]
                if len(names) != len(set(names)):
                    self.errors.append(f"Mood file {mood_file.name}: duplicate mood names")

            except (ValueError, TypeError, KeyError, RuntimeError) as e:
                self.errors.append(f"Mood file {mood_file.name}: {e}")

    def _validate_linguistic_styles(self) -> None:
        """Validate linguistic style configurations."""
        styles_dir = self.config_dir / "linguistic_styles"
        if not styles_dir.exists():
            return

        for style_file in styles_dir.glob("*.json"):
            try:
                style = LinguisticStyle.from_json(style_file)

                if not style.nicknames_for_user:
                    self.warnings.append(f"Style {style_file.stem}: no nicknames defined")

                if not style.kaomoji_lexicon:
                    self.warnings.append(f"Style {style_file.stem}: no kaomoji defined")

            except (ValueError, TypeError, KeyError, RuntimeError) as e:
                self.errors.append(f"Style {style_file.stem}: {e}")

    def get_report(self) -> dict[str, Any]:
        """Get validation report.

        Returns:
            Dictionary with errors and warnings
        """
        return {
            "valid": len(self.errors) == 0,
            "errors": self.errors,
            "warnings": self.warnings,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }

    def print_report(self) -> None:
        """Print validation report to console."""
        from rich.console import Console
        from rich.panel import Panel

        console = Console()
        report = self.get_report()

        if report["valid"] and not report["warnings"]:
            console.print(Panel("[green]✓ Configuration valid[/green]", title="Validation"))
        elif report["valid"]:
            console.print(
                Panel(
                    f"[yellow]⚠ {report['warning_count']} warning(s)[/yellow]", title="Validation"
                )
            )
            for warning in self.warnings:
                console.print(f"  [yellow]⚠ {warning}[/yellow]")
        else:
            console.print(
                Panel(
                    f"[red]✗ {report['error_count']} error(s), {report['warning_count']} warning(s)[/red]",
                    title="Validation",
                )
            )
            for error in self.errors:
                console.print(f"  [red]✗ {error}[/red]")
            for warning in self.warnings:
                console.print(f"  [yellow]⚠ {warning}[/yellow]")


def validate_config(config_dir: Path | str = "config") -> bool:
    """Quick validation of configuration.

    Args:
        config_dir: Path to configuration directory

    Returns:
        True if valid, False otherwise
    """
    validator = ConfigValidator(config_dir)
    is_valid = validator.validate_all()
    validator.print_report()
    return is_valid
