"use client";

interface GameHeaderProps {
  playerName: string;
  score: number;
  round: number;
  totalRounds: number;
  status: "active" | "completed" | "interrupted";
}

/**
 * Displays the current game state: player name, score, round progress,
 * and game status indicator.
 */
export function GameHeader({
  playerName,
  score,
  round,
  totalRounds,
  status,
}: GameHeaderProps) {
  const progressPercent = totalRounds > 0 ? (round / totalRounds) * 100 : 0;
  const isActive = status === "active";
  const isCompleted = status === "completed";

  return (
    <div className="glass rounded-2xl p-6 space-y-4">
      {/* Top row: player name + status badge */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center text-white font-bold text-sm">
            {playerName.charAt(0).toUpperCase()}
          </div>
          <div>
            <p className="font-semibold text-white text-sm">{playerName}</p>
            <p className="text-xs text-gray-500">Player</p>
          </div>
        </div>

        <div
          className={`px-3 py-1 rounded-full text-xs font-medium ${
            isCompleted
              ? "bg-green-900/30 text-green-400 border border-green-800/30"
              : isActive
              ? "bg-brand-900/30 text-brand-400 border border-brand-800/30"
              : "bg-yellow-900/30 text-yellow-400 border border-yellow-800/30"
          }`}
        >
          <span className="flex items-center gap-1.5">
            {isActive && <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse" />}
            {status === "active" ? "In Progress" : status === "completed" ? "Completed" : "Interrupted"}
          </span>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-4">
        <div className="text-center">
          <p className="text-2xl font-bold text-white">{score}</p>
          <p className="text-xs text-gray-500 mt-1">Score</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-white">
            {round}
            <span className="text-sm text-gray-500 font-normal"> / {totalRounds}</span>
          </p>
          <p className="text-xs text-gray-500 mt-1">Round</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-brand-400">
            {Math.max(0, totalRounds - round)}
          </p>
          <p className="text-xs text-gray-500 mt-1">Remaining</p>
        </div>
      </div>

      {/* Progress bar */}
      <div className="w-full h-1.5 rounded-full bg-gray-800 overflow-hidden">
        <div
          className="h-full rounded-full bg-gradient-to-r from-brand-600 to-accent-500 transition-all duration-500 ease-out"
          style={{ width: `${Math.min(progressPercent, 100)}%` }}
        />
      </div>
    </div>
  );
}
