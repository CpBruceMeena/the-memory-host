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
  score: number;
  current_round: number;
  session_id: string;
  created_at: string;
}

export interface LeaderboardResponse {
  leaderboard: LeaderboardEntry[];
}

export interface RoundResponse {
  round_number: number;
  expected: string[];
  user_response: string[] | null;
  is_correct: boolean | null;
}

export interface RoundsListResponse {
  rounds: RoundResponse[];
}

export interface HealthResponse {
  status: string;
  version: string;
}

// ── BFF Proxy Functions (called from server components / route handlers) ──

/** HTTP request timeout in milliseconds (5 seconds). */
const REQUEST_TIMEOUT_MS = 5_000;

/**
 * Fetch with an AbortController timeout.
 * Throws a descriptive error if the backend is unreachable.
 */
async function fetchWithTimeout(url: string, options: RequestInit = {}): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const res = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    return res;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Extract a human-readable error message from a failed API response.
 *
 * Tries JSON body (FastAPI standard `detail` field), falls back to
 * HTTP status + raw response text (truncated to 200 chars).
 */
async function extractError(res: Response): Promise<string> {
  // Read body as text FIRST, then try JSON — the body stream can
  // only be consumed once, so reading with .json() first would
  // leave nothing for .text() in the fallback path.
  const text = await res.text();
  try {
    const body = JSON.parse(text);
    return body?.detail || body?.message || `HTTP ${res.status}`;
  } catch {
    return text
      ? `HTTP ${res.status}: ${text.slice(0, 200)}`
      : `HTTP ${res.status} (empty response)`;
  }
}

/**
 * Create a new game session via the backend.
 */
export async function createSession(
  playerName: string
): Promise<CreateSessionResponse> {
  const res = await fetchWithTimeout(`${BACKEND_URL}/api/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player_name: playerName } satisfies CreateSessionRequest),
  });

  if (!res.ok) {
    throw new Error(await extractError(res));
  }

  return res.json();
}

/**
 * Get the current state of a game session.
 */
export async function getSession(
  sessionId: string
): Promise<SessionResponse> {
  const res = await fetchWithTimeout(`${BACKEND_URL}/api/sessions/${sessionId}`, {
    next: { revalidate: 0 }, // Never cache — always fetch fresh
  });

  if (!res.ok) {
    throw new Error(await extractError(res));
  }

  return res.json();
}

/**
 * Get all rounds for a game session.
 */
export async function getSessionRounds(
  sessionId: string
): Promise<RoundsListResponse> {
  const res = await fetchWithTimeout(
    `${BACKEND_URL}/api/sessions/${sessionId}/rounds`,
    { next: { revalidate: 0 } }
  );

  if (!res.ok) {
    throw new Error(await extractError(res));
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
  const res = await fetchWithTimeout(`${BACKEND_URL}/api/sessions/${sessionId}/end`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason } satisfies EndSessionRequest),
  });

  if (!res.ok) {
    throw new Error(await extractError(res));
  }

  return res.json();
}

/**
 * Fetch the leaderboard from the backend.
 */
export async function getLeaderboard(): Promise<LeaderboardResponse> {
  const res = await fetchWithTimeout(`${BACKEND_URL}/api/leaderboard`, {
    next: { revalidate: 0 }, // Never cache — always fetch fresh
  });

  if (!res.ok) {
    throw new Error(await extractError(res));
  }

  return res.json();
}

/**
 * Health check.
 */
export async function healthCheck(): Promise<HealthResponse> {
  const res = await fetchWithTimeout(`${BACKEND_URL}/api/health`, {
    next: { revalidate: 30 },
  });

  if (!res.ok) {
    throw new Error("Backend unhealthy");
  }

  return res.json();
}
