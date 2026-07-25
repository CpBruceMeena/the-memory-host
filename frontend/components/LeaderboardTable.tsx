"use client";

import type { LeaderboardEntry } from "@/lib/api";

interface LeaderboardTableProps {
  /** Array of leaderboard entries (may be empty). */
  entries: LeaderboardEntry[];
  /** True while data is being loaded. */
  isLoading?: boolean;
  /** Error message if fetch failed. */
  error?: string | null;
  /** Callback to refresh the data. */
  onRefresh?: () => void;
}

/**
 * Displays a ranked leaderboard table with player stats.
 * Shows gold/silver/bronze styling for top 3.
 */
export function LeaderboardTable({
  entries,
  isLoading = false,
  error = null,
  onRefresh,
}: LeaderboardTableProps) {
  if (isLoading) {
    return (
      <div className="glass rounded-2xl p-8 text-center">
        <div className="space-y-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4">
              <div className="skeleton w-8 h-8 rounded-full" />
              <div className="skeleton h-4 flex-1" />
              <div className="skeleton h-4 w-16" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass rounded-2xl p-8 text-center">
        <div className="px-4 py-3 rounded-xl bg-red-900/20 border border-red-800/30 text-sm text-red-400 mb-4">
          {error}
        </div>
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="text-sm text-brand-400 hover:text-brand-300 transition-colors"
          >
            Try again
          </button>
        )}
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div className="glass rounded-2xl p-8 text-center">
        <div className="text-3xl mb-3">🏆</div>
        <h3 className="text-lg font-semibold text-white mb-1">No scores yet</h3>
        <p className="text-sm text-gray-500">
          Be the first to play and set a high score!
        </p>
      </div>
    );
  }

  return (
    <div className="glass rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/5">
        <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
          Top Players
        </h3>
      </div>

      {/* Table */}
      <div className="divide-y divide-white/5">
        {entries.map((entry, index) => (
          <div
            key={entry.player_name}
            className={`flex items-center gap-4 px-6 py-4 transition-colors hover:bg-white/[0.02] ${
              index < 3 ? "bg-white/[0.02]" : ""
            }`}
          >
            {/* Rank */}
            <div className="w-8 flex-shrink-0 text-center">
              {index === 0 ? (
                <span className="text-lg">🥇</span>
              ) : index === 1 ? (
                <span className="text-lg">🥈</span>
              ) : index === 2 ? (
                <span className="text-lg">🥉</span>
              ) : (
                <span className="text-sm text-gray-500 font-mono">
                  #{index + 1}
                </span>
              )}
            </div>

            {/* Player info */}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">
                {entry.player_name}
              </p>
              <p className="text-xs text-gray-500">
                {new Date(entry.created_at).toLocaleDateString()}
              </p>
            </div>

            {/* Score */}
            <div className="text-right flex-shrink-0">
              <p className="text-sm font-bold text-white">{entry.score}</p>
              <p className="text-xs text-gray-500">
                Round {entry.current_round}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
