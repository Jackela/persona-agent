"""Run offline service integration checks and propagate pytest's exit status."""

import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
args = sys.argv[1:] or ["tests/integration"]
raise SystemExit(
    subprocess.call([sys.executable, "-m", "pytest", *args, "-v", "--timeout=180"], cwd=root)
)
