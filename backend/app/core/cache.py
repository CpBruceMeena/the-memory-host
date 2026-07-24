"""In-memory cache layer using TTLCache.

Replaces Redis for simplicity — no external infrastructure needed.
Used for:
- Active session data (30 min TTL)
- Round state (30 min TTL)
- Leaderboard (60 second TTL)
- Session lookup by room name
"""

from __future__ import annotations

from typing import Any, Optional

from cachetools import TTLCache

from app.core.config import settings


class GameCache:
    """In-memory cache for game data with TTL-based expiration."""

    def __init__(self) -> None:
        # Active session data: 30 min TTL, max 100 sessions
        self._active_sessions: TTLCache[str, dict[str, Any]] = TTLCache(
            maxsize=settings.CACHE_MAX_ACTIVE_SESSIONS,
            ttl=settings.CACHE_ACTIVE_SESSION_TTL,
        )

        # Round state: 30 min TTL, max 500 rounds
        self._round_cache: TTLCache[str, dict[str, Any]] = TTLCache(
            maxsize=settings.CACHE_MAX_ROUNDS,
            ttl=settings.CACHE_ROUND_TTL,
        )

        # Leaderboard: 60 second TTL
        self._leaderboard_cache: TTLCache[str, list[dict[str, Any]]] = TTLCache(
            maxsize=10,
            ttl=settings.CACHE_LEADERBOARD_TTL,
        )

        # Room name → session ID lookup (30 min TTL, max 100)
        self._room_to_session: TTLCache[str, str] = TTLCache(
            maxsize=100,
            ttl=settings.CACHE_ACTIVE_SESSION_TTL,
        )

    # ── Active Sessions ──────────────────────────────────────────

    def set_session(self, session_id: str, data: dict[str, Any]) -> None:
        """Cache a session's data."""
        self._active_sessions[session_id] = data

    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        """Get cached session data, or None if not found/expired."""
        return self._active_sessions.get(session_id)

    def remove_session(self, session_id: str) -> None:
        """Remove a session from cache (e.g. on game end)."""
        self._active_sessions.pop(session_id, None)

    def session_exists(self, session_id: str) -> bool:
        """Check if a session is in the active cache."""
        return session_id in self._active_sessions

    # ── Room → Session Mapping ───────────────────────────────────

    def set_room_session(self, room_name: str, session_id: str) -> None:
        """Map a room name to its session ID."""
        self._room_to_session[room_name] = session_id

    def get_session_by_room(self, room_name: str) -> Optional[str]:
        """Get session ID for a room name."""
        return self._room_to_session.get(room_name)

    # ── Round Cache ──────────────────────────────────────────────

    def set_round(self, session_id: str, round_number: int, data: dict[str, Any]) -> None:
        """Cache a round's state."""
        key = f"session:{session_id}:round:{round_number}"
        self._round_cache[key] = data

    def get_round(self, session_id: str, round_number: int) -> Optional[dict[str, Any]]:
        """Get cached round state, or None if not found/expired."""
        key = f"session:{session_id}:round:{round_number}"
        return self._round_cache.get(key)

    # ── Leaderboard ──────────────────────────────────────────────

    def set_leaderboard(self, data: list[dict[str, Any]]) -> None:
        """Cache the leaderboard (top scores)."""
        self._leaderboard_cache["leaderboard"] = data

    def get_leaderboard(self) -> Optional[list[dict[str, Any]]]:
        """Get cached leaderboard, or None if expired."""
        return self._leaderboard_cache.get("leaderboard")

    def is_leaderboard_stale(self) -> bool:
        """Check if leaderboard cache is expired/empty."""
        return "leaderboard" not in self._leaderboard_cache

    def invalidate_leaderboard(self) -> None:
        """Force leaderboard cache invalidation.

        Call this after a round is scored to ensure the leaderboard
        reflects the latest data on next fetch.
        """
        self._leaderboard_cache.pop("leaderboard", None)


# Singleton instance
cache = GameCache()
