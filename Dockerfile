FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Copy build configuration first for better layer caching
COPY pyproject.toml setup.py LICENSE README.md ./
COPY src/ ./src/

# Install project in editable mode with dev dependencies
RUN pip install --no-cache-dir -e ".[dev]"

# Expose the application port
EXPOSE 8080

# Healthcheck endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Run the web UI
CMD ["python", "-m", "persona_agent.ui.cli", "web", "--host", "0.0.0.0", "--port", "8080"]
