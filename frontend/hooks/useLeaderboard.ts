"use client";

import { useCallback, useEffect, useState } from "react";

import type { LeaderboardEntry } from "@/lib/api";

interface UseLeaderboardResult {
  /** The leaderboard entries, or null if not yet loaded. */
  leaderboard: LeaderboardEntry[] | null;
  /** True while the initial fetch is in progress. */
  isLoading: boolean;
  /** Error message if the last fetch failed. */
  error: string | null;
  /** Manually refresh the leaderboard. */
  refresh: () => Promise<void>;
}

/**
 * Fetches the leaderboard from the backend.
 *
 * @param refreshInterval - Auto-refresh interval in ms (default 0 = no auto-refresh).
 */
export function useLeaderboard(
  refreshInterval: number = 0
): UseLeaderboardResult {
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[] | null>(
    null
  );
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLeaderboard = useCallback(async () => {
    try {
      const res = await fetch("/api/leaderboard", {
        cache: "no-store",
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const data = await res.json();
      setLeaderboard(data.leaderboard ?? []);
      setError(null);
    } catch (err) {
      console.error("Leaderboard fetch error:", err);
      setError(err instanceof Error ? err.message : "Failed to fetch");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLeaderboard();

    if (refreshInterval > 0) {
      const interval = setInterval(fetchLeaderboard, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [fetchLeaderboard, refreshInterval]);

  return {
    leaderboard,
    isLoading,
    error,
    refresh: fetchLeaderboard,
  };
}
