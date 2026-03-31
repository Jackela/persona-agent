#!/usr/bin/env python3
"""Quick test to verify Pixel config loads correctly."""

import sys

sys.path.insert(0, "/mnt/d/Code/Persona-agent/src")

from pathlib import Path

# Test 1: Load Pixel character
print("Test 1: Loading Pixel character...")
try:
    from persona_agent.config.schemas.character import CharacterProfile

    pixel = CharacterProfile.from_yaml(
        Path("/mnt/d/Code/Persona-agent/config/characters/pixel.yaml")
    )
    print(f"✓ Pixel loaded: {pixel.name}")
    print(f"  - Relationship: {pixel.relationship}")
    print(f"  - Physical height: {pixel.physical.height if pixel.physical else 'N/A'}")
    print(f"  - Core memories: {len(pixel.core_memories)}")
except Exception as e:
    print(f"✗ Failed: {e}")
    import traceback

    traceback.print_exc()

# Test 2: Load Pixel moods
print("\nTest 2: Loading Pixel moods...")
try:
    from persona_agent.config.schemas.mood import MoodDefinition

    moods = MoodDefinition.from_markdown(
        Path("/mnt/d/Code/Persona-agent/config/mood_states/pixel_moods.md")
    )
    print(f"✓ Loaded {len(moods)} mood states")
    for mood in moods:
        print(f"  - {mood.name}: {mood.display_name}")
except Exception as e:
    print(f"✗ Failed: {e}")
    import traceback

    traceback.print_exc()

# Test 3: Load Pixel linguistic style
print("\nTest 3: Loading Pixel linguistic style...")
try:
    from persona_agent.config.schemas.linguistic import LinguisticStyle

    style = LinguisticStyle.from_json(
        Path("/mnt/d/Code/Persona-agent/config/linguistic_styles/pixel_style.json")
    )
    print(f"✓ Style loaded: {len(style.nicknames_for_user)} nicknames")
    print(f"  - Kaomoji categories: {len(style.kaomoji_lexicon)}")
except Exception as e:
    print(f"✗ Failed: {e}")
    import traceback

    traceback.print_exc()

# Test 4: Create PersonaManager with Pixel
print("\nTest 4: Creating PersonaManager with Pixel...")
try:
    from persona_agent.config.loader import ConfigLoader
    from persona_agent.core.persona_manager import PersonaManager

    loader = ConfigLoader(Path("/mnt/d/Code/Persona-agent/config"))
    manager = PersonaManager(loader, "pixel")

    char = manager.get_character()
    print(f"✓ PersonaManager created with: {char.name}")

    mood_engine = manager.get_mood_engine()
    print(f"  - Mood engine moods: {len(mood_engine.moods)}")

    prompt = manager.build_system_prompt()
    print(f"  - System prompt length: {len(prompt)} chars")
except Exception as e:
    print(f"✗ Failed: {e}")
    import traceback

    traceback.print_exc()

print("\n" + "=" * 50)
print("Pixel configuration verification complete!")
print("=" * 50)
