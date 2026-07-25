"use client";

import { useEffect, useState } from "react";

import { GameLog } from "@/components/GameLog";

interface RoundEntry {
  round_number: number;
  expected: string[];
  user_response: string[] | null;
  is_correct: boolean | null;
}

interface RoundHistoryProps {
  sessionId: string | null;
  /** How often to poll for new rounds (ms). Default 5000. */
  pollInterval?: number;
}

/**
 * Fetches round history from the REST API and renders GameLog.
 *
 * Polls every `pollInterval` ms so new rounds appear automatically
 * as the user plays through the game.
 */
export function RoundHistory({
  sessionId,
  pollInterval = 4000,
}: RoundHistoryProps) {
  const [rounds, setRounds] = useState<RoundEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) return;

    let cancelled = false;

    const fetchRounds = async () => {
      try {
        const res = await fetch(`/api/sessions/${sessionId}/rounds`, {
          cache: "no-store",
        });
        if (!res.ok) {
          const body = await res.text();
          console.warn("Failed to fetch rounds:", body);
          return;
        }
        const data = await res.json();
        if (!cancelled) {
          setRounds(data.rounds ?? []);
          setError(null);
        }
      } catch (err) {
        console.warn("Round fetch error:", err);
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load rounds");
        }
      }
    };

    // Initial fetch
    fetchRounds();

    // Poll for new rounds
    const interval = setInterval(fetchRounds, pollInterval);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [sessionId, pollInterval]);

  // Format the API data into what GameLog expects
  const formattedRounds = rounds.map((r) => ({
    round_number: r.round_number,
    expected: r.expected,
    actual: r.user_response ?? null,
    correct: r.is_correct ?? null,
  }));

  return <GameLog rounds={formattedRounds} maxEntries={10} />;
}
