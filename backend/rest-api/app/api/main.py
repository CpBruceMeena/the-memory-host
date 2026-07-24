"""FastAPI application entrypoint for The Memory Host — REST API service.

This is the REST API server (port 8000):
- Session CRUD
- Leaderboard
- Health

It communicates with the game-engine service (port 3002) to start voice bot sessions.
No Signaling/WebRTC — that lives in the game-engine service.
"""

import logging
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

logger = logging.getLogger(__name__)

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
