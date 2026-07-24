"use client";

import { useLeaderboard } from "@/hooks/useLeaderboard";
import { LeaderboardTable } from "@/components/LeaderboardTable";

export default function LeaderboardPage() {
  const { leaderboard, isLoading, error, refresh } = useLeaderboard(30000); // Auto-refresh every 30s

  return (
    <div className="max-w-lg mx-auto px-4 pt-8 pb-24 space-y-6 animate-fade-in">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-bold text-white mb-2">
          <span className="text-gradient">Leaderboard</span>
        </h1>
        <p className="text-sm text-gray-500">
          The top memory masters
        </p>
      </div>

      {/* Refresh button */}
      <div className="flex justify-end">
        <button
          onClick={refresh}
          disabled={isLoading}
          className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-white transition-colors disabled:opacity-50"
        >
          <svg
            className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M1 4v6h6M23 20v-6h-6" />
            <path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15" />
          </svg>
          Refresh
        </button>
      </div>

      {/* Leaderboard Table */}
      <LeaderboardTable
        entries={leaderboard ?? []}
        isLoading={isLoading}
        error={error}
        onRefresh={refresh}
      />

      {/* Link back home */}
      <div className="text-center pt-4">
        <a
          href="/"
          className="text-sm text-brand-400 hover:text-brand-300 transition-colors"
        >
          ← Back to Home
        </a>
      </div>
    </div>
  );
}
