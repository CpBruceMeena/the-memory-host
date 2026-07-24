"""FastAPI application entrypoint for The Memory Host — REST API service.

This is the REST API server (port 8000):
- Session CRUD
- Leaderboard
- Health

It communicates with the game-engine service (port 3002) to start voice bot sessions.
No Signaling/WebRTC — that lives in the game-engine service.
"""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

# ── Logging: stdout + single file at project root ────────────────────────
LOG_FILE = Path(__file__).resolve().parent.parent.parent.parent.parent / "app.log"

_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setFormatter(_formatter)

_file_handler = logging.FileHandler(str(LOG_FILE), mode="a", encoding="utf-8")
_file_handler.setFormatter(_formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[_stdout_handler, _file_handler],
    force=True,
)

logger = logging.getLogger(__name__)
logger.info("Logging to %s", LOG_FILE)

app = FastAPI(
    title="The Memory Host — REST API",
    description="REST API for session management, leaderboard, and health.",
    version="1.0.0",
)

# CORS — allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "http://localhost:3001",  # Game-engine signaling
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(router, prefix="/api")

# Startup timestamp
app.state.startup_time = datetime.now(timezone.utc)
