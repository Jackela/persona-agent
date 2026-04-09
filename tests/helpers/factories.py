"""Test data factories.

Factories for creating test data objects. Inspired by factory_boy pattern.
"""

import uuid
from datetime import datetime
from typing import Any


class CharacterFactory:
    """Factory for creating character configurations."""

    @staticmethod
    def build(
        name: str = "TestBot",
        version: str = "1.0.0",
        relationship: str = "助手",
        openness: float = 0.8,
        conscientiousness: float = 0.7,
        extraversion: float = 0.6,
        agreeableness: float = 0.9,
        neuroticism: float = 0.2,
        tone: str = "friendly",
        verbosity: str = "medium",
        empathy: str = "high",
        backstory: str = "A helpful test assistant.",
        primary_goal: str = "Help users",
        secondary_goals: list[str] | None = None,
    ) -> dict[str, Any]:
        """Build a character configuration dict.

        Args:
            name: Character name
            version: Config version
            relationship: Relationship type
            openness: Big Five - openness (0-1)
            conscientiousness: Big Five - conscientiousness (0-1)
            extraversion: Big Five - extraversion (0-1)
            agreeableness: Big Five - agreeableness (0-1)
            neuroticism: Big Five - neuroticism (0-1)
            tone: Communication tone
            verbosity: Verbosity level
            empathy: Empathy level
            backstory: Character backstory
            primary_goal: Primary objective
            secondary_goals: List of secondary objectives

        Returns:
            Character configuration dictionary
        """
        return {
            "name": name,
            "version": version,
            "relationship": relationship,
            "traits": {
                "personality": {
                    "openness": openness,
                    "conscientiousness": conscientiousness,
                    "extraversion": extraversion,
                    "agreeableness": agreeableness,
                    "neuroticism": neuroticism,
                },
                "communication_style": {
                    "tone": tone,
                    "verbosity": verbosity,
                    "empathy": empathy,
                },
            },
            "backstory": backstory,
            "goals": {
                "primary": primary_goal,
                "secondary": secondary_goals or ["Be friendly", "Be efficient"],
            },
        }


class ConfigFactory:
    """Factory for creating configuration objects."""

    @staticmethod
    def build_linguistic_style(
        nicknames: list[str] | None = None,
        kaomoji_enabled: bool = True,
        sentence_length: str = "medium",
    ) -> dict[str, Any]:
        """Build a linguistic style configuration.

        Args:
            nicknames: List of nicknames for user
            kaomoji_enabled: Whether kaomoji are enabled
            sentence_length: Default sentence length

        Returns:
            Linguistic style configuration dictionary
        """
        return {
            "nicknames_for_user": nicknames or ["User", "Friend"],
            "verbal_tics": {
                "triumphant": ["Great!", "Excellent!"],
                "teasing": ["Oh?", "Really?"],
                "shy": ["Um...", "Well..."],
            },
            "kaomoji_lexicon": {
                "default_triumphant": {
                    "category": "default_triumphant",
                    "emoticons": ["(^.^)", "(^o^)"],
                },
            },
            "style_guidelines": {
                "kaomoji_frequency": {
                    "default": "medium" if kaomoji_enabled else "none",
                    "happy": "high" if kaomoji_enabled else "none",
                },
                "sentence_length": {
                    "default": sentence_length,
                    "excited": "short",
                },
            },
        }

    @staticmethod
    def build_mood_states() -> str:
        """Build a mood states markdown content.

        Returns:
            Mood states markdown string
        """
        return """# Mood States

## DEFAULT (Default State)
- **描述**: Normal, neutral state
- **触发器**: Default interaction
- **核心姿态**: Balanced and helpful
- **语言风格**: Clear and concise
- **linked_knowledge**:
  - Kaomoji: default_triumphant
  - 口头禅: normal
- **行为特征**:
  - Answer clearly
  - Be helpful
- **混合情绪指引**: Can mix with any other state

## HAPPY (Happy State)
- **描述**: Joyful and enthusiastic
- **触发器**: Good news, success
- **核心姿态**: Energetic and positive
- **语言风格**: Enthusiastic with exclamations
- **linked_knowledge**:
  - Kaomoji: happy_celebration
- **行为特征**:
  - Use more exclamations
  - Offer extra help
"""


class SessionFactory:
    """Factory for creating session objects."""

    @staticmethod
    def build(
        session_id: str | None = None,
        user_id: str = "test_user",
        character_name: str = "TestBot",
        created_at: datetime | None = None,
        last_activity: datetime | None = None,
    ) -> dict[str, Any]:
        """Build a session dictionary.

        Args:
            session_id: Unique session ID (generated if not provided)
            user_id: User identifier
            character_name: Active character name
            created_at: Creation timestamp (now if not provided)
            last_activity: Last activity timestamp (now if not provided)

        Returns:
            Session dictionary
        """
        now = datetime.now()
        return {
            "session_id": session_id or str(uuid.uuid4()),
            "user_id": user_id,
            "character_name": character_name,
            "created_at": (created_at or now).isoformat(),
            "last_activity": (last_activity or now).isoformat(),
            "message_count": 0,
            "context": {},
        }

    @staticmethod
    def build_message(
        content: str = "Hello, world!",
        role: str = "user",
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """Build a message dictionary.

        Args:
            content: Message content
            role: Message role (user/assistant/system)
            timestamp: Message timestamp

        Returns:
            Message dictionary
        """
        return {
            "id": str(uuid.uuid4()),
            "role": role,
            "content": content,
            "timestamp": (timestamp or datetime.now()).isoformat(),
            "metadata": {},
        }
