# Persona-Agent Project - OpenCode Configuration

## Project Overview

**Name**: Persona-Agent  
**Type**: Python AI Agent Framework  
**Purpose**: Local role-playing AI agent with dynamic persona switching, mood management, and linguistic style customization

## Architecture

```
persona-agent/
├── src/persona_agent/         # Core source code
│   ├── core/                  # Core engine (persona, mood, memory)
│   ├── config/                # Configuration system
│   ├── skills/                # Skill system (lazy loading)
│   ├── mcp/                   # MCP integrations
│   └── ui/                    # CLI interface
├── config/                    # Configuration files
├── skills/                    # Custom user skills
├── memory/                    # Memory storage
└── tests/                     # Test suite
```

## Development Guidelines

### Code Standards
- **Formatter**: Black (line-length: 100)
- **Linter**: Ruff
- **Type Checker**: mypy (strict mode)
- **Python Version**: 3.11+

### Key Commands
```bash
# Development setup
pip install -e ".[dev]"

# Testing
pytest -v                    # Run all tests
pytest --cov=src            # With coverage
pytest tests/test_file.py   # Specific test

# Code quality
black src tests             # Format
ruff check src tests        # Lint
mypy src                    # Type check
pre-commit run --all-files  # Pre-commit hooks

# Run the application
persona-agent chat          # Start chat
pa chat --persona companion # With specific persona
```

### Project Patterns

#### 1. Configuration System
- Characters: YAML files in `config/characters/`
- Mood states: Markdown in `config/mood_states/`
- Linguistic styles: JSON in `config/linguistic_styles/`

#### 2. Skill System
- Lazy loading architecture
- Skills inherit from `BaseSkill`
- Located in `src/persona_agent/skills/` or `skills/` (user)

#### 3. Testing Pattern
```python
# tests/test_example.py
import pytest
from persona_agent.core.persona import Persona

@pytest.fixture
def sample_persona():
    return Persona.from_yaml("config/characters/default.yaml")

def test_persona_loading(sample_persona):
    assert sample_persona.name is not None
```

## AI Agent Instructions

### When Working on This Project

1. **Always run tests after changes**
   ```bash
   pytest -xvs tests/test_<modified_module>.py
   ```

2. **Follow existing patterns**
   - Check similar files before creating new ones
   - Use Pydantic models for data validation
   - Use Rich for CLI output
   - Use async/await for I/O operations

3. **Configuration Changes**
   - Update example configs in `config/`
   - Validate YAML/JSON syntax
   - Test with actual persona-agent run

4. **Adding Skills**
   - Inherit from `BaseSkill`
   - Implement `execute()` method
   - Add to `skills/` directory
   - Include tests in `tests/skills/`

5. **MCP Integration**
   - Place in `src/persona_agent/mcp/`
   - Follow existing client patterns
   - Document required environment variables

### Testing Strategy

1. **Unit Tests**: Core logic, isolated
2. **Integration Tests**: Full workflows
3. **E2E Tests**: CLI commands

### Common Tasks

#### Adding a New Persona
1. Create YAML in `config/characters/`
2. Define mood states in `config/mood_states/`
3. Create linguistic style in `config/linguistic_styles/`
4. Test: `persona-agent chat --persona <name>`

#### Adding a Skill
1. Create file in `skills/` or `src/persona_agent/skills/`
2. Inherit from `BaseSkill`
3. Implement required methods
4. Add tests
5. Register in skill registry

#### Debugging
- Use `rich` for pretty printing
- Add `--verbose` flag support
- Check `memory/` for persistence issues

## External Dependencies

### API Keys (Environment Variables)
```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Database
- ChromaDB for vector storage
- SQLite for session memory

## CI/CD

GitHub Actions workflow runs:
1. Lint (ruff, black check)
2. Type check (mypy)
3. Tests (pytest)
4. Coverage (codecov)

## Related Files

- `ARCHITECTURE_ANALYSIS.md` - Detailed architecture
- `IMPLEMENTATION_GUIDE.md` - Implementation details
- `PROJECT_PLAN.md` - Development roadmap
- `CI_GUIDE.md` - CI/CD documentation

## Notes

- Project uses Hatchling build system
- Pre-commit hooks enforce code quality
- Coverage reports uploaded to Codecov
- MIT Licensed
