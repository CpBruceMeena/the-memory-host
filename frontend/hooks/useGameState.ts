"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { SessionResponse } from "@/lib/api";

interface UseGameStateResult {
  /** The current game state, or null if not yet loaded. */
  gameState: SessionResponse | null;
  /** True while the initial fetch is in progress. */
  isLoading: boolean;
  /** Error message if the last fetch failed. */
  error: string | null;
  /** Manually trigger a re-fetch. */
  refetch: () => Promise<void>;
  /** Stop polling (e.g. when game ends). */
  stopPolling: () => void;
}

/**
 * Polls the game session state every 2 seconds.
 *
 * Automatically stops polling when the game status is no longer "active".
 *
 * @param sessionId - The game session UUID (null to disable).
 * @param pollInterval - Polling interval in ms (default 2000).
 */
export function useGameState(
  sessionId: string | null,
  pollInterval: number = 2000
): UseGameStateResult {
  const [gameState, setGameState] = useState<SessionResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const activeRef = useRef(true);

  const fetchState = useCallback(async () => {
    if (!sessionId) return;

    try {
      const res = await fetch(`/api/sessions/${sessionId}`, {
        cache: "no-store",
      });

      if (!res.ok) {
        // Try to extract the backend's error detail from the response body
        let detail = `HTTP ${res.status}`;
        try {
          const body = await res.json();
          if (body?.detail) {
            detail = body.detail;
          }
        } catch {
          // Response body isn't JSON — use the fallback message
        }

        if (res.status === 404) {
          setError("Session not found");
          return;
        }
        throw new Error(detail);
      }

      const data: SessionResponse = await res.json();
      setGameState(data);
      setError(null);
      setIsLoading(false);

      // Stop polling if game has ended
      if (data.status !== "active" && activeRef.current) {
        activeRef.current = false;
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      }
    } catch (err) {
      console.error("Game state polling error:", err);
      setError(err instanceof Error ? err.message : "Failed to fetch");
    }
  }, [sessionId]);

  // Start / stop polling based on sessionId
  useEffect(() => {
    if (!sessionId) {
      setIsLoading(false);
      return;
    }

    activeRef.current = true;
    setIsLoading(true);

    // Initial fetch
    fetchState();

    // Set up polling interval
    intervalRef.current = setInterval(fetchState, pollInterval);

    return () => {
      activeRef.current = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [sessionId, pollInterval, fetchState]);

  const stopPolling = useCallback(() => {
    activeRef.current = false;
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  return {
    gameState,
    isLoading,
    error,
    refetch: fetchState,
    stopPolling,
  };
}
