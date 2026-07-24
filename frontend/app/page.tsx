/**
 * Landing page — create or join a game session.
 *
 * Wrapped in Suspense to support useSearchParams() for the ?name= pre-fill.
 */
"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function HomePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialName = searchParams.get("name") || "";

  const [playerName, setPlayerName] = useState(initialName);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleStartGame = async (e: React.FormEvent) => {
    e.preventDefault();

    const name = playerName.trim();
    if (!name) return;

    setIsCreating(true);
    setError(null);

    try {
      const res = await fetch("/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ player_name: name }),
      });

      if (!res.ok) {
        const err = await res
          .json()
          .catch(() => ({ detail: "Failed to create session" }));
        throw new Error(err.detail || "Something went wrong");
      }

      const data = await res.json();

      // Store room connection info so the game page can use it
      if (typeof window !== "undefined") {
        sessionStorage.setItem("room_url", data.room_url);
        sessionStorage.setItem("room_token", data.room_token);
      }

      router.push(`/game/${data.session_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start game");
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <>
      {/* Hero */}
      <div className="text-center max-w-2xl mx-auto mb-12">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full glass text-xs text-brand-400 mb-6">
          <span className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse" />
          Voice-Powered Memory Game
        </div>

        <h1 className="text-5xl md:text-6xl font-bold tracking-tight mb-4">
          <span className="text-gradient">The Memory Host</span>
        </h1>

        <p className="text-lg text-gray-400 leading-relaxed max-w-lg mx-auto">
          Listen to sequences of words spoken aloud, then repeat them back from
          memory. Each round adds another word. How far can you go?
        </p>
      </div>

      {/* Start Game Form */}
      <form
        onSubmit={handleStartGame}
        className="w-full max-w-md mx-auto glass rounded-2xl p-8 space-y-6"
      >
        <div className="space-y-2">
          <label
            htmlFor="player-name"
            className="block text-sm font-medium text-gray-300"
          >
            Enter your name to begin
          </label>
          <input
            id="player-name"
            type="text"
            value={playerName}
            onChange={(e) => setPlayerName(e.target.value)}
            placeholder="Your name..."
            maxLength={100}
            required
            disabled={isCreating}
            className="w-full px-4 py-3 rounded-xl bg-surface-light border border-gray-700 
                       text-white placeholder-gray-500 
                       focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent
                       disabled:opacity-50 disabled:cursor-not-allowed
                       transition-all duration-200"
          />
        </div>

        {error && (
          <div className="px-4 py-3 rounded-xl bg-red-900/20 border border-red-800/30 text-sm text-red-400 animate-slide-up">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={isCreating || !playerName.trim()}
          className="w-full py-3 px-6 rounded-xl font-semibold text-white
                     bg-gradient-to-r from-brand-600 to-brand-500
                     hover:from-brand-500 hover:to-brand-400
                     disabled:opacity-40 disabled:cursor-not-allowed
                     transition-all duration-200 animate-pulse-glow
                     focus:outline-none focus:ring-2 focus:ring-brand-400 focus:ring-offset-2 focus:ring-offset-surface"
        >
          {isCreating ? (
            <span className="flex items-center justify-center gap-2">
              <svg
                className="animate-spin h-4 w-4"
                viewBox="0 0 24 24"
                fill="none"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              Starting game...
            </span>
          ) : (
            "Start Game"
          )}
        </button>
      </form>

      {/* Features */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-16 max-w-3xl mx-auto w-full">
        {[
          {
            title: "Listen",
            description:
              "The bot speaks a sequence of words for you to remember.",
            icon: "🎧",
          },
          {
            title: "Repeat",
            description:
              "Say the words back in the exact same order using your voice.",
            icon: "🎙️",
          },
          {
            title: "Progress",
            description:
              "Each correct answer adds a new word to the sequence. 10 rounds to master!",
            icon: "🏆",
          },
        ].map((feature) => (
          <div
            key={feature.title}
            className="glass rounded-xl p-6 text-center hover:bg-white/[0.06] transition-colors duration-200"
          >
            <div className="text-3xl mb-3">{feature.icon}</div>
            <h3 className="font-semibold text-white mb-2">{feature.title}</h3>
            <p className="text-sm text-gray-400 leading-relaxed">
              {feature.description}
            </p>
          </div>
        ))}
      </div>
    </>
  );
}

export default function HomePage() {
  return (
    <div className="flex flex-col items-center justify-center px-6 pt-16 pb-24 animate-fade-in">
      <Suspense fallback={null}>
        <HomePageContent />
      </Suspense>
    </div>
  );
}
