"""Pydantic models for API request/response schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Request Schemas ──────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    """Request body for POST /api/sessions."""

    player_name: str = Field(
        ..., min_length=1, max_length=100, description="Player's display name"
    )


class EndSessionRequest(BaseModel):
    """Request body for POST /api/sessions/{id}/end (optional)."""

    reason: Optional[str] = Field(
        None, description="Reason for ending (e.g. 'manual', 'timeout')"
    )


# ── Response Schemas ─────────────────────────────────────────

class SessionResponse(BaseModel):
    """Response for GET /api/sessions/{id}."""

    session_id: str = Field(..., description="Unique session identifier")
    player_name: str = Field(..., description="Player's display name")
    status: str = Field(..., description="'active' | 'completed' | 'interrupted'")
    score: int = Field(..., description="Current score")
    current_round: int = Field(..., description="Current round number")
    total_rounds: int = Field(..., description="Maximum number of rounds")
    created_at: datetime = Field(..., description="Session creation timestamp")
    ended_at: Optional[datetime] = Field(None, description="Session end timestamp")


class CreateSessionResponse(BaseModel):
    """Response for POST /api/sessions (201)."""

    session_id: str = Field(..., description="Unique session identifier")
    player_name: str = Field(..., description="Player's display name")
    room_url: str = Field(..., description="SmallWebRTC room URL")
    room_token: str = Field(..., description="Room access token")
    status: str = Field(..., description="'active'")
    created_at: datetime = Field(..., description="Session creation timestamp")


class LeaderboardEntry(BaseModel):
    """A single entry in the leaderboard."""

    player_name: str = Field(..., description="Player's display name")
    best_score: int = Field(..., description="Highest score achieved")
    best_round: int = Field(..., description="Highest round reached")
    games_played: int = Field(..., description="Total games played")
    last_played: datetime = Field(..., description="Most recent game date")


class LeaderboardResponse(BaseModel):
    """Response for GET /api/leaderboard."""

    leaderboard: list[LeaderboardEntry] = Field(
        default_factory=list, description="Sorted leaderboard entries"
    )


class HealthResponse(BaseModel):
    """Response for GET /api/health."""

    status: str = Field(..., description="Service health status")
    version: str = Field(..., description="API version")


class RoundResponse(BaseModel):
    """Response for a single round entry."""

    round_number: int = Field(..., description="Round number (1-indexed)")
    expected: list[str] = Field(..., description="Expected word sequence")
    user_response: Optional[list[str]] = Field(None, description="User's spoken words")
    is_correct: Optional[bool] = Field(None, description="True/False if answered, null if pending")


class RoundsListResponse(BaseModel):
    """Response for GET /api/sessions/{id}/rounds."""

    rounds: list[RoundResponse] = Field(
        default_factory=list, description="All rounds for this session"
    )


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str = Field(..., description="Error description")
    error_code: Optional[str] = Field(None, description="Machine-readable error code")
