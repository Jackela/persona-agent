#!/usr/bin/env python3
"""Full system verification script."""

import sys
import asyncio

sys.path.insert(0, "/mnt/d/Code/Persona-agent/src")

from pathlib import Path
import tempfile


def test_imports():
    """Test that all modules can be imported."""
    print("=" * 60)
    print("Test 1: Module Imports")
    print("=" * 60)

    try:
        from persona_agent.config.schemas.character import CharacterProfile
        from persona_agent.config.schemas.linguistic import LinguisticStyle
        from persona_agent.config.schemas.mood import MoodDefinition
        from persona_agent.config.loader import ConfigLoader
        from persona_agent.core.memory_store import MemoryStore
        from persona_agent.core.mood_engine import MoodEngine
        from persona_agent.core.persona_manager import PersonaManager
        from persona_agent.core.agent_engine import AgentEngine
        from persona_agent.utils.llm_client import LLMClient

        print("✓ All core modules imported successfully")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_config_system():
    """Test configuration system."""
    print("\n" + "=" * 60)
    print("Test 2: Configuration System")
    print("=" * 60)

    try:
        from persona_agent.config.schemas.character import CharacterProfile, PersonalityTraits

        # Test basic profile creation
        profile = CharacterProfile(
            name="TestBot",
            version="1.0.0",
            traits={"personality": {"openness": 0.8}},
            backstory="Test",
            goals={"primary": "Help"},
        )
        print(f"✓ CharacterProfile created: {profile.name}")

        # Test linguistic style
        from persona_agent.config.schemas.linguistic import LinguisticStyle

        style_path = Path("/mnt/c/Users/k7407/OneDrive/linguistic_style.json")
        if style_path.exists():
            style = LinguisticStyle.from_json(style_path)
            print(f"✓ Linguistic style loaded: {len(style.nicknames_for_user)} nicknames")
            print(f"  - Kaomoji categories: {len(style.kaomoji_lexicon)}")
        else:
            print("⚠ Linguistic style file not found (WSL path)")

        return True
    except Exception as e:
        print(f"✗ Config system test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_memory_system():
    """Test memory system."""
    print("\n" + "=" * 60)
    print("Test 3: Memory System (Honcho-inspired)")
    print("=" * 60)

    try:
        from persona_agent.core.memory_store import MemoryStore
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            memory = MemoryStore(db_path)

            # Test storing
            asyncio.run(
                memory.store(
                    session_id="test_session", user_message="Hello", assistant_message="Hi there!"
                )
            )
            print("✓ Memory stored successfully")

            # Test retrieval
            memories = asyncio.run(memory.retrieve_recent("test_session"))
            print(f"✓ Retrieved {len(memories)} memories")

            # Test user model
            user_model = asyncio.run(memory.get_or_create_user_model("test_user"))
            print(f"✓ User model created: {user_model.user_id}")

        return True
    except Exception as e:
        print(f"✗ Memory system test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_mood_engine():
    """Test mood engine."""
    print("\n" + "=" * 60)
    print("Test 4: Mood Engine")
    print("=" * 60)

    try:
        from persona_agent.core.mood_engine import MoodEngine

        engine = MoodEngine()
        print(f"✓ MoodEngine created with {len(engine.moods)} moods")

        # Test mood update
        engine.update("Hello")
        print(f"✓ Current mood: {engine.current_state.name}")

        # Test emotion triggers
        engine.update("I'm really sad today")
        print(f"✓ Mood after sad input: {engine.current_state.name}")

        # Test prompt modifier
        modifier = engine.get_prompt_modifier()
        if modifier:
            print(f"✓ Prompt modifier generated ({len(modifier)} chars)")

        return True
    except Exception as e:
        print(f"✗ Mood engine test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_persona_manager():
    """Test persona manager."""
    print("\n" + "=" * 60)
    print("Test 5: Persona Manager")
    print("=" * 60)

    try:
        from persona_agent.config.loader import ConfigLoader
        from persona_agent.core.persona_manager import PersonaManager
        from persona_agent.config.schemas.character import CharacterProfile
        import tempfile
        import yaml

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test config
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            (config_dir / "characters").mkdir()

            char_data = {
                "name": "TestAssistant",
                "version": "1.0.0",
                "relationship": "Friend",
                "traits": {"personality": {"openness": 0.7, "conscientiousness": 0.8}},
                "backstory": "A helpful test assistant",
                "goals": {"primary": "Be helpful"},
            }

            char_file = config_dir / "characters" / "test.yaml"
            with open(char_file, "w") as f:
                yaml.dump(char_data, f)

            loader = ConfigLoader(config_dir)
            manager = PersonaManager(loader, "test")

            char = manager.get_character()
            print(f"✓ Persona loaded: {char.name}")

            # Test prompt building
            prompt = manager.build_system_prompt()
            print(f"✓ System prompt built ({len(prompt)} chars)")

        return True
    except Exception as e:
        print(f"✗ Persona manager test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_agent_engine():
    """Test agent engine."""
    print("\n" + "=" * 60)
    print("Test 6: Agent Engine")
    print("=" * 60)

    try:
        from persona_agent.core.agent_engine import AgentEngine
        from persona_agent.core.persona_manager import PersonaManager
        from persona_agent.core.memory_store import MemoryStore

        engine = AgentEngine(
            persona_manager=PersonaManager(), memory_store=MemoryStore(), session_id="test_session"
        )

        info = engine.get_session_info()
        print(f"✓ AgentEngine created")
        print(f"  - Session ID: {info['session_id'][:8]}...")

        return True
    except Exception as e:
        print(f"✗ Agent engine test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_cli():
    """Test CLI interface."""
    print("\n" + "=" * 60)
    print("Test 7: CLI Interface")
    print("=" * 60)

    try:
        from persona_agent.ui.cli import cli
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        if result.exit_code == 0:
            print("✓ CLI help displayed successfully")
        else:
            print(f"⚠ CLI help exit code: {result.exit_code}")

        return True
    except Exception as e:
        print(f"✗ CLI test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("PERSONA-AGENT FULL SYSTEM VERIFICATION")
    print("=" * 60)

    results = []

    results.append(("Module Imports", test_imports()))
    results.append(("Configuration System", test_config_system()))
    results.append(("Memory System", test_memory_system()))
    results.append(("Mood Engine", test_mood_engine()))
    results.append(("Persona Manager", test_persona_manager()))
    results.append(("Agent Engine", test_agent_engine()))
    results.append(("CLI Interface", test_cli()))

    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print("\n" + "-" * 60)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
