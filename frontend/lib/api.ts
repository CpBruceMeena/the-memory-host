"use server";

/**
 * API client for The Memory Host backend.
 *
 * All calls go through the Next.js BFF layer (/api/*), which proxies
 * to the FastAPI backend. This keeps API keys and internal URLs
 * server-side.
 */

const BACKEND_URL = process.env.BACKEND_API_URL || "http://localhost:8000";

// ── Types ─────────────────────────────────────────────────

export interface CreateSessionRequest {
  player_name: string;
}

export interface CreateSessionResponse {
  session_id: string;
  player_name: string;
  room_url: string;
  room_token: string;
  status: string;
  created_at: string;
}

export interface SessionResponse {
  session_id: string;
  player_name: string;
  status: "active" | "completed" | "interrupted";
  score: number;
  current_round: number;
  total_rounds: number;
  created_at: string;
  ended_at?: string | null;
}

export interface EndSessionRequest {
  reason?: string;
}

export interface LeaderboardEntry {
  player_name: string;
  best_score: number;
  best_round: number;
  games_played: number;
  last_played: string;
}

export interface LeaderboardResponse {
  leaderboard: LeaderboardEntry[];
}

export interface HealthResponse {
  status: string;
  version: string;
}

// ── BFF Proxy Functions (called from server components / route handlers) ──

/**
 * Create a new game session via the backend.
 */
export async function createSession(
  playerName: string
): Promise<CreateSessionResponse> {
  const res = await fetch(`${BACKEND_URL}/api/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player_name: playerName } satisfies CreateSessionRequest),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || "Failed to create session");
  }

  return res.json();
}

/**
 * Get the current state of a game session.
 */
export async function getSession(
  sessionId: string
): Promise<SessionResponse> {
  const res = await fetch(`${BACKEND_URL}/api/sessions/${sessionId}`, {
    next: { revalidate: 0 }, // Never cache — always fetch fresh
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || "Failed to fetch session");
  }

  return res.json();
}

/**
 * End a game session.
 */
export async function endSession(
  sessionId: string,
  reason?: string
): Promise<SessionResponse> {
  const res = await fetch(`${BACKEND_URL}/api/sessions/${sessionId}/end`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason } satisfies EndSessionRequest),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || "Failed to end session");
  }

  return res.json();
}

/**
 * Fetch the leaderboard from the backend.
 */
export async function getLeaderboard(): Promise<LeaderboardResponse> {
  const res = await fetch(`${BACKEND_URL}/api/leaderboard`, {
    next: { revalidate: 60 }, // Cache for 60 seconds
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || "Failed to fetch leaderboard");
  }

  return res.json();
}

/**
 * Health check.
 */
export async function healthCheck(): Promise<HealthResponse> {
  const res = await fetch(`${BACKEND_URL}/api/health`, {
    next: { revalidate: 30 },
  });

  if (!res.ok) {
    throw new Error("Backend unhealthy");
  }

  return res.json();
}
