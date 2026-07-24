"""FastAPI application entrypoint for The Memory Host backend."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown events."""
    # Startup: could initialize connections, warm caches, etc.
    app.state.startup_time = __import__("datetime").datetime.now()
    yield
    # Shutdown: could clean up connections
    # Engine disposal happens automatically on process exit


app = FastAPI(
    title="The Memory Host",
    description="Voice-based Memory Card Game — Backend API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "http://localhost:3001",  # SmallWebRTC signaling
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(router, prefix="/api")
