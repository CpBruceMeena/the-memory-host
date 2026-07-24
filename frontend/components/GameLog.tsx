"use client";

interface RoundEntry {
  round_number: number;
  expected: string[];
  actual: string[] | null;
  correct: boolean | null;
}

interface GameLogProps {
  /** Round history entries (empty for a fresh game). */
  rounds?: RoundEntry[];
  /** Maximum entries to show (default: all). */
  maxEntries?: number;
}

/**
 * Displays a scrollable log of past rounds, showing what was expected
 * vs what the user said.
 */
export function GameLog({ rounds = [], maxEntries }: GameLogProps) {
  const displayed = maxEntries ? rounds.slice(-maxEntries) : rounds;

  if (displayed.length === 0) {
    return (
      <div className="glass rounded-2xl p-6 text-center">
        <p className="text-sm text-gray-500">No rounds played yet.</p>
        <p className="text-xs text-gray-600 mt-1">
          The round history will appear here as you play.
        </p>
      </div>
    );
  }

  return (
    <div className="glass rounded-2xl p-6 space-y-3">
      <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
        Round History
      </h3>

      <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
        {displayed.map((round) => (
          <div
            key={round.round_number}
            className={`rounded-xl p-4 border ${
              round.correct === true
                ? "bg-green-900/10 border-green-800/20"
                : round.correct === false
                ? "bg-red-900/10 border-red-800/20"
                : "bg-gray-800/30 border-gray-700/20"
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-gray-400">
                Round {round.round_number}
              </span>
              <span
                className={`text-xs font-medium ${
                  round.correct === true
                    ? "text-green-400"
                    : round.correct === false
                    ? "text-red-400"
                    : "text-yellow-400"
                }`}
              >
                {round.correct === true
                  ? "✅ Correct"
                  : round.correct === false
                  ? "❌ Wrong"
                  : "⏳ Pending"}
              </span>
            </div>

            <div className="space-y-1 text-sm">
              <div className="flex items-start gap-2">
                <span className="text-brand-400 w-16 shrink-0 text-xs">Expected:</span>
                <span className="text-gray-300">{round.expected.join(", ")}</span>
              </div>

              {round.actual && (
                <div className="flex items-start gap-2">
                  <span className="text-accent-400 w-16 shrink-0 text-xs">You said:</span>
                  <span
                    className={
                      round.correct ? "text-green-300" : "text-red-300"
                    }
                  >
                    {round.actual.join(", ")}
                  </span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
