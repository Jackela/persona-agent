"""Linguistic style schema definitions."""

import json
import random
from pathlib import Path

from pydantic import BaseModel, Field


class VerbalTics(BaseModel):
    """Verbal tics organized by mood/state."""

    triumphant: list[str] = Field(default_factory=list)  # 得意时
    teasing: list[str] = Field(default_factory=list)  # 戏谑时
    shy: list[str] = Field(default_factory=list)  # 害羞时


class KaomojiCategory(BaseModel):
    """A category of kaomoji emoticons."""

    category: str
    emoticons: list[str]

    def get_random(self) -> str | None:
        """Get a random kaomoji from this category."""
        if self.emoticons:
            return random.choice(self.emoticons)
        return None


class StyleGuidelines(BaseModel):
    """Guidelines for applying linguistic style."""

    kaomoji_frequency: dict[str, str] = Field(default_factory=dict)
    sentence_length: dict[str, str] = Field(default_factory=dict)


class LinguisticStyle(BaseModel):
    """Complete linguistic style configuration.

    Defines how the character speaks, including:
    - Nicknames for the user
    - Verbal tics by mood
    - Kaomoji (Japanese emoticon) lexicon
    - Style guidelines
    """

    nicknames_for_user: list[str] = Field(default_factory=list)
    verbal_tics: VerbalTics = Field(default_factory=VerbalTics)
    kaomoji_lexicon: dict[str, KaomojiCategory] = Field(default_factory=dict)
    style_guidelines: StyleGuidelines | None = None

    @classmethod
    def from_json(cls, path: Path) -> "LinguisticStyle":
        """Load linguistic style from JSON file.

        Args:
            path: Path to the JSON configuration file

        Returns:
            LinguisticStyle instance

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the JSON is invalid
        """
        if not path.exists():
            raise FileNotFoundError(f"Linguistic style not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        # Convert kaomoji_lexicon from nested dicts to KaomojiCategory objects
        if "kaomoji_lexicon" in data:
            lexicon = {}
            for key, value in data["kaomoji_lexicon"].items():
                if isinstance(value, dict):
                    lexicon[key] = KaomojiCategory(**value)
                elif isinstance(value, list):
                    lexicon[key] = KaomojiCategory(category=key, emoticons=value)
            data["kaomoji_lexicon"] = lexicon

        return cls(**data)

    def get_kaomoji(self, category: str) -> str | None:
        """Get a random kaomoji from a category.

        Args:
            category: The kaomoji category name

        Returns:
            A random kaomoji or None if category not found
        """
        if category in self.kaomoji_lexicon:
            return self.kaomoji_lexicon[category].get_random()
        return None

    def get_nickname(self) -> str:
        """Get a random nickname for the user.

        Returns:
            A random nickname or "你" if none defined
        """
        if self.nicknames_for_user:
            return random.choice(self.nicknames_for_user)
        return "你"

    def get_verbal_tic(self, mood: str) -> str | None:
        """Get a verbal tic appropriate for the given mood.

        Args:
            mood: The current mood/state

        Returns:
            A verbal tic or None
        """
        tics = []
        if mood in ["triumphant", "competitive", "victorious"]:
            tics = self.verbal_tics.triumphant
        elif mood in ["teasing", "playful", "default"]:
            tics = self.verbal_tics.teasing
        elif mood in ["shy", "embarrassed", "moe"]:
            tics = self.verbal_tics.shy

        if tics:
            return random.choice(tics)
        return None

    def get_kaomoji_for_mood(self, mood: str) -> str | None:
        """Get an appropriate kaomoji for the given mood.

        Maps mood names to kaomoji categories.

        Args:
            mood: The current mood/state

        Returns:
            An appropriate kaomoji or None
        """
        mood_to_category = {
            # Default states
            "default": "default_triumphant",
            "playful": "default_teasing",
            "impatient": "default_impatient_playful",
            # Moe states
            "moe_panic": "moe_panic",
            "moe_shy": "moe_shy",
            "moe_tsundere": "moe_tsundere_stubborn",
            # Caring states
            "caring_gentle": "caring_gentle",
            "caring_tsundere": "caring_tsundere_bossy",
            # Competitive states
            "competitive": "competitive_showoff",
            # Jealousy states
            "jealous": "jealousy_sulking",
            # Melancholy states
            "melancholy": "melancholy_calm",
        }

        category = mood_to_category.get(mood)
        if category:
            return self.get_kaomoji(category)

        # Fallback: try to match partial names
        for key in self.kaomoji_lexicon:
            if mood.lower() in key.lower() or key.lower() in mood.lower():
                return self.get_kaomoji(key)

        return None

    def apply_to_text(
        self,
        text: str,
        mood: str = "default",
        use_kaomoji: bool = True,
        use_nickname: bool = False,
    ) -> str:
        """Apply linguistic style to text.

        Args:
            text: The base text to style
            mood: Current mood for selecting appropriate elements
            use_kaomoji: Whether to append kaomoji
            use_nickname: Whether to replace "你" with a nickname

        Returns:
            Styled text
        """
        result = text

        # Replace "你" with nickname if requested
        if use_nickname and "你" in result:
            nickname = self.get_nickname()
            # Only replace some occurrences to avoid overuse
            if random.random() < 0.3:
                result = result.replace("你", nickname, 1)

        # Add kaomoji if enabled
        if use_kaomoji:
            kaomoji = self.get_kaomoji_for_mood(mood)
            if kaomoji and kaomoji not in result:
                # Append kaomoji at the end or insert naturally
                if result.endswith(("！", "!", "？", "?", "~")):
                    result += kaomoji
                else:
                    result += " " + kaomoji

        return result
