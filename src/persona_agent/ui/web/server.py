"""Web UI server for Persona Agent."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Persona Agent Web UI", version="0.1.0")

_STATIC_DIR = Path(__file__).parent / "static"

app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
