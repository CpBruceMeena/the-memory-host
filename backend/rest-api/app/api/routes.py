"""FastAPI API routes — session management, leaderboard, health.

Communicates with the game-engine service to start voice bot sessions.
"""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DbSession
from app.api.schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    EndSessionRequest,
    ErrorResponse,
    HealthResponse,
    LeaderboardEntry,
    LeaderboardResponse,
    RoundResponse,
    RoundsListResponse,
    SessionResponse,
)
from app.core.config import settings
from app.models.round import Round
from app.models.session import Session

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Health ───────────────────────────────────────────────────

@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        version="1.0.0",
    )


# ── Sessions ─────────────────────────────────────────────────

@router.post(
    "/sessions",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Sessions"],
    responses={
        400: {"model": ErrorResponse},
    },
)
async def create_session(
    body: CreateSessionRequest,
    db: DbSession,
):
    """Create a new game session.

    Creates a database record, notifies the game-engine service
    to start the voice bot, and returns session info to the frontend.
    """
    # If the player already has an active session, mark it as
    # interrupted so we don't accumulate orphaned active sessions.
    existing = await db.execute(
        select(Session).where(
            Session.player_name == body.player_name,
            Session.status == "active",
        )
    )
    old_session = existing.scalar_one_or_none()
    if old_session:
        old_session.status = "interrupted"
        old_session.ended_at = datetime.now(timezone.utc)
        logger.info(
            "Closed previous active session %s for player '%s'",
            old_session.id,
            body.player_name,
        )

    # Create session with placeholder room info (will update after
    # we have the session_id for consistent room naming with bot.py)
    db_session = Session(
        player_name=body.player_name,
        status="active",
        score=0,
        current_round=0,
        max_rounds=10,
        room_url="",
        room_name="",
    )
    db.add(db_session)
    await db.flush()
    await db.refresh(db_session)

    # Now we have the session_id — use it for room naming (matching bot.py)
    room_name = f"memory-game-{str(db_session.id)[:8]}"
    room_url = f"http://localhost:3001/room/{room_name}"

    # Update session with real room info
    db_session.room_url = room_url
    db_session.room_name = room_name
    await db.flush()

    # Notify the game-engine service to start the voice bot
    async def _notify_game_engine() -> None:
        """Send start-session request to the game-engine service."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{settings.GAME_ENGINE_URL}/start-session",
                    json={
                        "session_id": str(db_session.id),
                        "player_name": body.player_name,
                    },
                    timeout=5.0,
                )
                if resp.status_code == 200:
                    logger.info(
                        "Game engine started for session %s", db_session.id
                    )
                else:
                    logger.warning(
                        "Game engine returned %d for session %s: %s",
                        resp.status_code,
                        db_session.id,
                        resp.text,
                    )
        except httpx.RequestError as e:
            logger.error(
                "Failed to notify game-engine for session %s: %s",
                db_session.id,
                e,
            )

    asyncio.create_task(_notify_game_engine())

    return CreateSessionResponse(
        session_id=str(db_session.id),
        player_name=db_session.player_name,
        room_url=room_url,
        room_token="placeholder-token",
        status="active",
        created_at=db_session.created_at,
    )


@router.get(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    tags=["Sessions"],
    responses={
        404: {"model": ErrorResponse},
    },
)
async def get_session(
    session_id: UUID,
    db: DbSession,
):
    """Get the current state of a game session.

    Always reads from database (no cache) to ensure fresh data
    when the game-engine updates scores between frontend polls.
    """
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    db_session = result.scalar_one_or_none()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    return SessionResponse(
        session_id=str(db_session.id),
        player_name=db_session.player_name,
        status=db_session.status,
        score=db_session.score,
        current_round=db_session.current_round,
        total_rounds=db_session.max_rounds,
        created_at=db_session.created_at,
        ended_at=db_session.ended_at,
    )


@router.post(
    "/sessions/{session_id}/end",
    response_model=SessionResponse,
    tags=["Sessions"],
    responses={
        404: {"model": ErrorResponse},
    },
)
async def end_session(
    session_id: UUID,
    body: EndSessionRequest,
    db: DbSession,
):
    """End an active session (manually or on game over)."""
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    db_session = result.scalar_one_or_none()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    if db_session.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session '{session_id}' is already {db_session.status}",
        )

    db_session.status = "completed"
    db_session.ended_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(db_session)

    return SessionResponse(
        session_id=str(db_session.id),
        player_name=db_session.player_name,
        status=db_session.status,
        score=db_session.score,
        current_round=db_session.current_round,
        total_rounds=db_session.max_rounds,
        created_at=db_session.created_at,
        ended_at=db_session.ended_at,
    )


# ── Leaderboard ──────────────────────────────────────────────

@router.get(
    "/sessions/{session_id}/rounds",
    response_model=RoundsListResponse,
    tags=["Sessions"],
    responses={
        404: {"model": ErrorResponse},
    },
)
async def get_session_rounds(
    session_id: UUID,
    db: DbSession,
):
    """Get all rounds for a game session.

    Returns round history including expected sequences and user responses.
    Used by the frontend to display round history in the GameLog.
    """
    result = await db.execute(
        select(Round).where(
            Round.session_id == session_id
        ).order_by(
            Round.round_number.asc()
        )
    )
    rounds = result.scalars().all()

    return RoundsListResponse(
        rounds=[
            RoundResponse(
                round_number=r.round_number,
                expected=r.word_sequence,
                user_response=r.user_response,
                is_correct=r.is_correct,
            )
            for r in rounds
        ]
    )


@router.get(
    "/leaderboard",
    response_model=LeaderboardResponse,
    tags=["Leaderboard"],
)
async def get_leaderboard(
    db: DbSession,
):
    """Get the top scores leaderboard.

    Queries database directly (no cache) for fresh results.
    """
    # Query from database
    result = await db.execute(
        select(Session).where(
            Session.status == "completed"
        ).order_by(
            Session.score.desc(),
            Session.current_round.desc(),
        ).limit(20)
    )
    sessions = result.scalars().all()

    # Show each completed session as its own leaderboard entry
    # (not grouped by player_name), so every individual game result
    # is visible. Sorted by score descending, then round descending.
    leaderboard_data = [
        {
            "player_name": s.player_name,
            "best_score": s.score,
            "best_round": s.current_round,
            "games_played": 1,
            "last_played": s.created_at,
        }
        for s in sessions
    ]

    return LeaderboardResponse(leaderboard=leaderboard_data)
