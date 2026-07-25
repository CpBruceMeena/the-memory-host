"use client";

import dynamic from "next/dynamic";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { GameHeader } from "@/components/GameHeader";
import { GameLog } from "@/components/GameLog";
import { GameOverModal } from "@/components/GameOverModal";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { useGameState } from "@/hooks/useGameState";

// SSR-safe dynamic import for the WebRTC component
const WebRTCRoom = dynamic(
  () =>
    import("@/components/WebRTCRoom").then((mod) => ({ default: mod.WebRTCRoom })),
  {
    ssr: false,
    loading: () => <LoadingSkeleton variant="card" lines={2} />,
  }
);

export default function GamePage() {
  const params = useParams();
  const sessionId = typeof params.sessionId === "string" ? params.sessionId : null;

  // Retrieve room connection info from sessionStorage (set during session creation)
  const [roomUrl, setRoomUrl] = useState<string | null>(null);
  const [roomToken, setRoomToken] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      setRoomUrl(sessionStorage.getItem("room_url"));
      setRoomToken(sessionStorage.getItem("room_token"));
    }
  }, []);

  const { gameState, isLoading, error } = useGameState(sessionId, 2000);

  // ── Game-start waiting state ──────────────────────────────
  // If the game loads but current_round stays 0 for a very long
  // time (45s), show a retry prompt instead of the old "Game
  // Didn't Start" error. The WebRTCRoom component handles
  // connection errors independently.
  const [showRetryPrompt, setShowRetryPrompt] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!gameState) return;

    // Game started before timeout — clear timer
    if (gameState.current_round > 0 && timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
      setShowRetryPrompt(false);
      return;
    }

    // Game hasn't started and timer not yet armed — start 45s timeout
    if (
      gameState.current_round === 0 &&
      gameState.status === "active" &&
      timerRef.current === null
    ) {
      timerRef.current = setTimeout(() => {
        setShowRetryPrompt(true);
      }, 45_000);
    }
  }, [gameState]);

  // Clear timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current !== null) clearTimeout(timerRef.current);
    };
  }, []);

  // Polling error state
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] px-6 animate-fade-in">
        <div className="glass rounded-2xl p-8 max-w-md w-full text-center">
          <div className="text-4xl mb-4">{"😕"}</div>
          <h2 className="text-xl font-bold text-white mb-2">Connection Error</h2>
          <p className="text-sm text-gray-400 mb-2">{error}</p>
          {error.toLowerCase().includes("fetch") ||
            error.toLowerCase().includes("timed out") ||
            error.toLowerCase().includes("aborted") ? (
            <p className="text-xs text-gray-500 mb-4">
              Make sure the backend server is running on port 8000
            </p>
          ) : null}
          <a
            href="/"
            className="inline-block py-2.5 px-6 rounded-xl font-medium text-white
                       bg-gradient-to-r from-brand-600 to-brand-500
                       hover:from-brand-500 hover:to-brand-400
                       transition-all duration-200"
          >
            Back to Home
          </a>
        </div>
      </div>
    );
  }

  // Loading state (initial)
  if (isLoading || !gameState) {
    return (
      <div className="max-w-lg mx-auto px-4 pt-8 pb-24">
        <LoadingSkeleton variant="page" lines={4} />
      </div>
    );
  }

  // Active game state
  const isGameOver = gameState.status !== "active";

  return (
    <div className="max-w-lg mx-auto px-4 pt-6 pb-24 space-y-6 animate-fade-in">
      {/* Game Header */}
      <GameHeader
        playerName={gameState.player_name}
        score={gameState.score}
        round={gameState.current_round}
        totalRounds={gameState.total_rounds}
        status={gameState.status}
      />

      {/* WebRTC Voice Connection */}
      <WebRTCRoom
        roomUrl={roomUrl ?? ""}
        token={roomToken ?? ""}
      />

      {/* Game Log */}
      <GameLog
        rounds={[]}
        maxEntries={10}
      />

      {/* Waiting indicator — shown when game hasn't started yet */}
      {!isGameOver && gameState.current_round === 0 && !showRetryPrompt && (
        <div className="text-center animate-fade-in">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass text-sm text-gray-400">
            <span className="w-2 h-2 rounded-full bg-brand-500 animate-pulse" />
            Waiting for game to start...
          </div>
          <p className="text-xs text-gray-600 mt-2">
            The bot should join within a few seconds. Check the Voice Connection
            panel above for status.
          </p>
        </div>
      )}

      {/* Retry prompt — shown after 45s if game never started */}
      {!isGameOver && gameState.current_round === 0 && showRetryPrompt && (
        <div className="text-center animate-fade-in">
          <div className="glass rounded-2xl p-6 max-w-sm mx-auto">
            <h3 className="text-sm font-semibold text-gray-300 mb-2">
              Still Waiting?
            </h3>
            <p className="text-xs text-gray-500 mb-4">
              The game is taking longer than expected to start.
              Try refreshing or go back to the home page.
            </p>
            <div className="flex gap-3 justify-center">
              <a
                href="/"
                className="inline-block py-2 px-5 rounded-xl font-medium text-sm text-white
                           bg-gradient-to-r from-brand-600 to-brand-500
                           hover:from-brand-500 hover:to-brand-400
                           transition-all duration-200"
              >
                Back to Home
              </a>
              <button
                onClick={() => {
                  setShowRetryPrompt(false);
                  window.location.reload();
                }}
                className="inline-block py-2 px-5 rounded-xl font-medium text-sm text-gray-300
                           bg-white/10 hover:bg-white/15 border border-gray-700
                           transition-all duration-200"
              >
                Retry
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Game Over Modal */}
      <GameOverModal
        isOpen={isGameOver}
        score={gameState.score}
        roundsPassed={gameState.current_round}
        totalRounds={gameState.total_rounds}
        isWin={gameState.current_round >= gameState.total_rounds}
        playerName={gameState.player_name}
      />
    </div>
  );
}
