#!/bin/bash
# Run all CI checks locally

set -e  # Exit on error

echo "========================================="
echo "Running CI Checks Locally"
echo "========================================="
echo ""

export PYTHONPATH=/mnt/d/Code/Persona-agent/src:$PYTHONPATH

echo "1. Checking code formatting with Black..."
black --check src tests || {
    echo "❌ Black formatting check failed. Run 'black src tests' to fix."
    exit 1
}
echo "✅ Black formatting check passed"
echo ""

echo "2. Running Ruff linter..."
ruff check src tests || {
    echo "❌ Ruff linting failed. Run 'ruff check src tests --fix' to auto-fix."
    exit 1
}
echo "✅ Ruff linting passed"
echo ""

echo "3. Running type checker (MyPy)..."
mypy src --strict || {
    echo "⚠️  MyPy found type errors (non-blocking for now)"
}
echo ""

echo "4. Running tests with coverage..."
pytest --cov=src/persona_agent --cov-fail-under=65 -q || {
    echo "❌ Tests failed or coverage below 70%"
    exit 1
}
echo "✅ Tests passed with sufficient coverage"
echo ""

echo "5. Running security checks with Bandit..."
bandit -r src -ll || {
    echo "⚠️  Bandit found security issues (check output above)"
}
echo ""

echo "========================================="
echo "✅ All Critical CI Checks Passed!"
echo "========================================="
