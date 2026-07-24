"use client";

import { useState } from "react";

interface PlayerNameFormProps {
  onSubmit: (name: string) => void | Promise<void>;
  isLoading?: boolean;
  /** Initial value for editing */
  initialValue?: string;
  /** Button label (default: "Start Game") */
  buttonLabel?: string;
}

/**
 * A simple player name input form with validation.
 * Used on the landing page and potentially for re-entry.
 */
export function PlayerNameForm({
  onSubmit,
  isLoading = false,
  initialValue = "",
  buttonLabel = "Start Game",
}: PlayerNameFormProps) {
  const [name, setName] = useState(initialValue);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();

    if (!trimmed) {
      setError("Please enter your name");
      return;
    }

    if (trimmed.length > 100) {
      setError("Name must be 100 characters or fewer");
      return;
    }

    setError(null);

    try {
      await onSubmit(trimmed);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="w-full space-y-4">
      <div className="space-y-2">
        <label
          htmlFor="player-name-input"
          className="block text-sm font-medium text-gray-300"
        >
          Your Name
        </label>
        <input
          id="player-name-input"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Enter your name..."
          maxLength={100}
          disabled={isLoading}
          className="w-full px-4 py-3 rounded-xl bg-surface-light border border-gray-700 
                     text-white placeholder-gray-500 
                     focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent
                     disabled:opacity-50 disabled:cursor-not-allowed
                     transition-all duration-200"
          autoFocus
        />
      </div>

      {error && (
        <p className="text-sm text-red-400 animate-slide-up">{error}</p>
      )}

      <button
        type="submit"
        disabled={isLoading || !name.trim()}
        className="w-full py-3 px-6 rounded-xl font-semibold text-white
                   bg-gradient-to-r from-brand-600 to-brand-500
                   hover:from-brand-500 hover:to-brand-400
                   disabled:opacity-40 disabled:cursor-not-allowed
                   transition-all duration-200
                   focus:outline-none focus:ring-2 focus:ring-brand-400 focus:ring-offset-2 focus:ring-offset-surface"
      >
        {isLoading ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Loading...
          </span>
        ) : (
          buttonLabel
        )}
      </button>
    </form>
  );
}
