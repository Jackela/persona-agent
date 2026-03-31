#!/usr/bin/env python3
"""Quick verification script for config system."""

import sys

sys.path.insert(0, "/mnt/d/Code/Persona-agent/src")

from pathlib import Path
import yaml

# Test 1: Import schemas
print("Test 1: Importing schemas...")
try:
    from persona_agent.config.schemas.character import CharacterProfile, PersonalityTraits
    from persona_agent.config.schemas.linguistic import LinguisticStyle
    from persona_agent.config.schemas.mood import MoodDefinition

    print("✓ All schemas imported successfully")
except Exception as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# Test 2: Create basic character profile
print("\nTest 2: Creating character profile...")
try:
    profile = CharacterProfile(
        name="TestBot",
        version="1.0.0",
        traits={
            "personality": {
                "openness": 0.8,
                "conscientiousness": 0.7,
                "extraversion": 0.6,
                "agreeableness": 0.9,
                "neuroticism": 0.2,
            }
        },
        backstory="A helpful test assistant.",
        goals={"primary": "Help users"},
    )
    print(f"✓ Created profile: {profile.name}")
    print(f"  - Openness: {profile.traits.personality.openness}")
except Exception as e:
    print(f"✗ Profile creation failed: {e}")
    sys.exit(1)

# Test 3: Load actual Pixel character
print("\nTest 3: Loading Pixel character profile...")
try:
    pixel_path = Path("/mnt/c/Users/k7407/OneDrive/character_profile.yaml")
    if pixel_path.exists():
        pixel = CharacterProfile.from_yaml(pixel_path)
        print(f"✓ Loaded Pixel: {pixel.name}")
        print(f"  - Relationship: {pixel.relationship}")
        if pixel.psychological_drivers:
            print(f"  - Has psychological drivers: ✓")
        print(f"  - Core memories: {len(pixel.core_memories)}")
    else:
        print("⚠ Pixel config not found (expected in WSL)")
except Exception as e:
    print(f"✗ Failed to load Pixel: {e}")
    import traceback

    traceback.print_exc()

# Test 4: Load linguistic style
print("\nTest 4: Loading linguistic style...")
try:
    style_path = Path("/mnt/c/Users/k7407/OneDrive/linguistic_style.json")
    if style_path.exists():
        style = LinguisticStyle.from_json(style_path)
        print(f"✓ Loaded linguistic style")
        print(f"  - Nicknames: {len(style.nicknames_for_user)}")
        print(f"  - Kaomoji categories: {len(style.kaomoji_lexicon)}")

        # Test kaomoji retrieval
        kaomoji = style.get_kaomoji("default_triumphant")
        if kaomoji:
            print(f"  - Sample kaomoji: {kaomoji}")
    else:
        print("⚠ Linguistic style not found (expected in WSL)")
except Exception as e:
    print(f"✗ Failed to load linguistic style: {e}")
    import traceback

    traceback.print_exc()

# Test 5: Test ConfigLoader
print("\nTest 5: Testing ConfigLoader...")
try:
    from persona_agent.config.loader import ConfigLoader

    # Create test config
    test_config = Path("/tmp/test_persona_config")
    test_config.mkdir(exist_ok=True)
    (test_config / "characters").mkdir(exist_ok=True)

    # Write test character
    test_char = {
        "name": "TestCharacter",
        "version": "1.0.0",
        "relationship": "Friend",
        "traits": {
            "personality": {
                "openness": 0.5,
                "conscientiousness": 0.5,
                "extraversion": 0.5,
                "agreeableness": 0.5,
                "neuroticism": 0.5,
            }
        },
        "backstory": "Test character",
        "goals": {"primary": "Be helpful"},
    }

    with open(test_config / "characters" / "test.yaml", "w") as f:
        yaml.dump(test_char, f)

    loader = ConfigLoader(config_dir=test_config)
    loaded = loader.load_character("test")
    print(f"✓ ConfigLoader works: {loaded.name}")
except Exception as e:
    print(f"✗ ConfigLoader failed: {e}")
    import traceback

    traceback.print_exc()

print("\n" + "=" * 50)
print("Configuration system verification complete!")
print("=" * 50)
