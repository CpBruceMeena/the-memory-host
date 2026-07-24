"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

interface GameOverModalProps {
  /** Whether the modal is visible. */
  isOpen: boolean;
  /** Final score achieved. */
  score: number;
  /** Number of rounds the player completed. */
  roundsPassed: number;
  /** Total available rounds. */
  totalRounds: number;
  /** Whether the game was won (completed all rounds). */
  isWin: boolean;
  /** Optional player name for the "Play Again" redirect. */
  playerName?: string;
}

/**
 * Modal overlay displayed when the game ends (correct win or wrong answer).
 * Shows final stats and a "Play Again" button.
 */
export function GameOverModal({
  isOpen,
  score,
  roundsPassed,
  totalRounds,
  isWin,
  playerName,
}: GameOverModalProps) {
  const router = useRouter();
  const [visible, setVisible] = useState(false);

  // Animate in when opened
  useEffect(() => {
    if (isOpen) {
      // Small delay for dramatic effect
      const timer = setTimeout(() => setVisible(true), 800);
      return () => clearTimeout(timer);
    } else {
      setVisible(false);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const percentage = totalRounds > 0 ? Math.round((roundsPassed / totalRounds) * 100) : 0;

  const handlePlayAgain = () => {
    if (playerName) {
      router.push(`/?name=${encodeURIComponent(playerName)}`);
    } else {
      router.push("/");
    }
  };

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center p-4 transition-all duration-500 ${
        visible ? "opacity-100" : "opacity-0"
      }`}
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={handlePlayAgain}
      />

      {/* Modal */}
      <div
        className={`relative glass rounded-3xl p-8 max-w-md w-full text-center transform transition-all duration-500 ${
          visible ? "scale-100 translate-y-0" : "scale-95 translate-y-4"
        }`}
      >
        {/* Icon */}
        <div className="text-5xl mb-4">
          {isWin ? "🏆" : roundsPassed >= totalRounds * 0.5 ? "🌟" : "💪"}
        </div>

        {/* Title */}
        <h2 className="text-2xl font-bold text-white mb-2">
          {isWin
            ? "You Won!"
            : roundsPassed >= totalRounds * 0.5
            ? "Great Effort!"
            : "Game Over"}
        </h2>

        <p className="text-gray-400 text-sm mb-6">
          {isWin
            ? "Incredible memory! You completed all rounds!"
            : `You made it through ${roundsPassed} of ${totalRounds} rounds.`}
        </p>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="glass rounded-xl p-4">
            <p className="text-2xl font-bold text-white">{score}</p>
            <p className="text-xs text-gray-500 mt-1">Score</p>
          </div>
          <div className="glass rounded-xl p-4">
            <p className="text-2xl font-bold text-white">{roundsPassed}</p>
            <p className="text-xs text-gray-500 mt-1">Rounds</p>
          </div>
          <div className="glass rounded-xl p-4">
            <p className="text-2xl font-bold text-brand-400">{percentage}%</p>
            <p className="text-xs text-gray-500 mt-1">Accuracy</p>
          </div>
        </div>

        {/* Play Again Button */}
        <button
          onClick={handlePlayAgain}
          className="w-full py-3 px-6 rounded-xl font-semibold text-white
                     bg-gradient-to-r from-brand-600 to-brand-500
                     hover:from-brand-500 hover:to-brand-400
                     transition-all duration-200
                     focus:outline-none focus:ring-2 focus:ring-brand-400 focus:ring-offset-2 focus:ring-offset-surface"
        >
          Play Again
        </button>

        <button
          onClick={() => router.push("/leaderboard")}
          className="w-full mt-3 py-2.5 px-6 rounded-xl font-medium text-gray-400
                     hover:text-white hover:bg-white/5
                     transition-all duration-200"
        >
          View Leaderboard
        </button>
      </div>
    </div>
  );
}
