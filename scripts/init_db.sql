-- ============================================
-- The Memory Host — Database Initialization
-- Run: psql -U postgres -f scripts/init_db.sql
-- ============================================

-- Create the database (run separately as superuser)
-- CREATE DATABASE "the-memory-host";

-- Connect to the target database
\c "the-memory-host"

-- ============================================
-- Sessions table
-- ============================================
CREATE TABLE IF NOT EXISTS sessions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_name         VARCHAR(100) NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'active',
        -- 'active' | 'completed' | 'interrupted'
    score               INTEGER NOT NULL DEFAULT 0,
    current_round       INTEGER NOT NULL DEFAULT 0,
    max_rounds          INTEGER NOT NULL DEFAULT 10,
    room_url            TEXT NOT NULL,
    room_name           VARCHAR(100) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at            TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at DESC);

-- ============================================
-- Rounds table
-- ============================================
CREATE TABLE IF NOT EXISTS rounds (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    round_number        INTEGER NOT NULL,
    word_sequence       JSONB NOT NULL,
        -- e.g. ["apple", "banana", "cat"]
    user_response       JSONB,
        -- e.g. ["apple", "banana", "cat"]; NULL if not yet answered
    is_correct          BOOLEAN,
        -- NULL = pending, TRUE = correct, FALSE = wrong
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    answered_at         TIMESTAMPTZ,

    -- Prevent double-scoring: one response per round
    CONSTRAINT uq_session_round UNIQUE (session_id, round_number)
);

CREATE INDEX IF NOT EXISTS idx_rounds_session ON rounds(session_id);

-- ============================================
-- Leaderboard view
-- ============================================
CREATE OR REPLACE VIEW leaderboard AS
SELECT
    s.player_name,
    MAX(s.score) AS best_score,
    MAX(s.current_round) AS best_round,
    COUNT(s.id) AS games_played,
    MAX(s.created_at) AS last_played
FROM sessions s
WHERE s.status = 'completed'
GROUP BY s.player_name
ORDER BY best_score DESC, best_round DESC;

-- ============================================
-- Created-at trigger for updated_at
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_sessions_updated_at ON sessions;
CREATE TRIGGER update_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
