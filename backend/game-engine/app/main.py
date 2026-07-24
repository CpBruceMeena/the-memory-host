"""The Memory Host — Game Engine Service Entry Point.

This service runs two servers concurrently:
1. WebSocket signaling server on port 3001 (for WebRTC)
2. FastAPI HTTP server on port 3002 (for start-session requests from the REST API)

The game engine receives session start requests from the REST API service
and runs the Pipecat voice bot for each session.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import websockets
from fastapi import FastAPI, Request
from pydantic import BaseModel

from app.core.config import settings
from app.services.bot import create_and_run_bot
from app.signaling.server import handle_connection

logger = logging.getLogger("game-engine")

# ── Startup diagnostics (print, not logger.info — runs before logging handlers are set up) ───
_dg_status = "✅ LOADED" if settings.DEEPGRAM_API_KEY else "❌ MISSING (set DEEPGRAM_API_KEY in .env)"
_dg_preview = settings.DEEPGRAM_API_KEY[:10] + "..." if settings.DEEPGRAM_API_KEY else ""
print("=" * 56, flush=True)
print("  The Memory Host — Game Engine Service", flush=True)
print(f"  DEEPGRAM_API_KEY: {_dg_status}", flush=True)
if settings.DEEPGRAM_API_KEY:
    print(f"    Key starts with: {_dg_preview}", flush=True)
print("  Signaling:          ws://0.0.0.0:3001", flush=True)
print(f"  HTTP:               http://{settings.HOST}:{settings.PORT}", flush=True)
print("=" * 56, flush=True)

SIGNALING_HOST = "0.0.0.0"
SIGNALING_PORT = 3001


class StartSessionRequest(BaseModel):
    session_id: str
    player_name: str = "Player"


# ── FastAPI App ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — start/stop signaling server alongside HTTP."""

    # ── Start WebSocket signaling server on port 3001 ───────────
    try:
        signaling_server = await websockets.serve(
            handle_connection, SIGNALING_HOST, SIGNALING_PORT
        )
        logger.info(
            "Signaling server started on ws://%s:%d",
            SIGNALING_HOST, SIGNALING_PORT,
        )
    except OSError as e:
        logger.warning(
            "Signaling server could not start on port %d: %s. "
            "WebRTC features will be unavailable.",
            SIGNALING_PORT, e,
        )
        signaling_server = None

    yield

    # ── Shutdown ────────────────────────────────────────────────
    if signaling_server:
        signaling_server.close()
        await signaling_server.wait_closed()
        logger.info("Signaling server stopped")


app = FastAPI(
    title="The Memory Host — Game Engine",
    description="Voice bot, game processor, and WebRTC signaling.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.post("/start-session")
async def start_session(body: StartSessionRequest):
    """Start a voice bot for the given session.

    Called by the REST API service after creating a session.
    The bot runs as a background task while this endpoint returns immediately.
    """
    logger.info(
        "Received start-session request: session=%s player=%s",
        body.session_id,
        body.player_name,
    )

    async def _run_bot() -> None:
        """Run the Pipecat voice bot for this session in the background."""
        try:
            await create_and_run_bot(
                session_id=body.session_id,
                player_name=body.player_name,
            )
        except Exception:
            logger.exception(
                "Bot failed for session %s", body.session_id
            )

    asyncio.create_task(_run_bot())

    return {"status": "ok", "session_id": body.session_id}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "game-engine"}
