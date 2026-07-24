"""FastAPI API routes — session management, leaderboard, health."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CacheDep, DbSession
from app.api.schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    EndSessionRequest,
    ErrorResponse,
    HealthResponse,
    LeaderboardEntry,
    LeaderboardResponse,
    SessionResponse,
)
from app.core.cache import GameCache
from app.models.round import Round
from app.models.session import Session

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
    cache: CacheDep,
):
    """Create a new game session.

    Creates a database record and caches the session data.
    SmallWebRTC room creation will be integrated here.
    """
    # Check if player has an active session already
    existing = await db.execute(
        select(Session).where(
            Session.player_name == body.player_name,
            Session.status == "active",
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Player '{body.player_name}' already has an active session",
        )

    # Create a placeholder room URL (SmallWebRTC integration in Phase 3)
    room_name = f"memory-game-{datetime.now(timezone.utc).timestamp():.0f}"
    room_url = f"http://localhost:3001/room/{room_name}"

    # Create session in database
    db_session = Session(
        player_name=body.player_name,
        status="active",
        score=0,
        current_round=0,
        max_rounds=10,
        room_url=room_url,
        room_name=room_name,
    )
    db.add(db_session)
    await db.flush()
    await db.refresh(db_session)

    # Cache session data
    session_data = {
        "session_id": str(db_session.id),
        "player_name": db_session.player_name,
        "status": db_session.status,
        "score": db_session.score,
        "current_round": db_session.current_round,
        "max_rounds": db_session.max_rounds,
        "room_url": db_session.room_url,
        "room_name": db_session.room_name,
    }
    cache.set_session(str(db_session.id), session_data)
    cache.set_room_session(room_name, str(db_session.id))

    return CreateSessionResponse(
        session_id=str(db_session.id),
        player_name=db_session.player_name,
        room_url=room_url,
        room_token="placeholder-token",  # Real token from SmallWebRTC in Phase 3
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
    cache: CacheDep,
):
    """Get the current state of a game session.

    Reads from cache first (fast), falls back to database.
    """
    sid = str(session_id)

    # Try cache first
    cached = cache.get_session(sid)
    if cached:
        return SessionResponse(
            session_id=cached["session_id"],
            player_name=cached["player_name"],
            status=cached["status"],
            score=cached["score"],
            current_round=cached["current_round"],
            total_rounds=cached["max_rounds"],
            created_at=datetime.fromisoformat(
                cached.get("created_at", datetime.now(timezone.utc).isoformat())
            ),
        )

    # Fallback to database
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    db_session = result.scalar_one_or_none()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    # Update cache
    session_data = {
        "session_id": str(db_session.id),
        "player_name": db_session.player_name,
        "status": db_session.status,
        "score": db_session.score,
        "current_round": db_session.current_round,
    }
    cache.set_session(sid, session_data)

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
    cache: CacheDep,
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

    # Remove from cache
    cache.remove_session(str(session_id))

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
    "/leaderboard",
    response_model=LeaderboardResponse,
    tags=["Leaderboard"],
)
async def get_leaderboard(
    db: DbSession,
    cache: CacheDep,
):
    """Get the top scores leaderboard.

    Served from cache if fresh (< 60s), otherwise queries the database.
    """
    # Try cache first
    if not cache.is_leaderboard_stale():
        cached = cache.get_leaderboard()
        if cached is not None:
            return LeaderboardResponse(leaderboard=cached)

    # Query from database using the leaderboard view
    result = await db.execute(
        select(Session).where(
            Session.status == "completed"
        ).order_by(
            Session.score.desc(),
            Session.current_round.desc(),
        ).limit(20)
    )
    sessions = result.scalars().all()

    # Build leaderboard by grouping by player_name
    player_scores: dict[str, dict] = {}
    for s in sessions:
        if s.player_name not in player_scores:
            player_scores[s.player_name] = {
                "player_name": s.player_name,
                "best_score": s.score,
                "best_round": s.current_round,
                "games_played": 0,
                "last_played": s.created_at,
            }
        entry = player_scores[s.player_name]
        entry["best_score"] = max(entry["best_score"], s.score)
        entry["best_round"] = max(entry["best_round"], s.current_round)
        entry["games_played"] += 1
        if s.created_at > entry["last_played"]:
            entry["last_played"] = s.created_at

    leaderboard_data = sorted(
        player_scores.values(),
        key=lambda x: (-x["best_score"], -x["best_round"]),
    )[:20]

    # Cache the result
    cache.set_leaderboard(leaderboard_data)

    return LeaderboardResponse(leaderboard=leaderboard_data)
