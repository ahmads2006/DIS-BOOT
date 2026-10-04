-- ============================================================================
-- ByteDaily Migration 003: bd_settings (persistent system key/value store)
-- ============================================================================
-- Stores leaderboard_message_id and other bot settings in Supabase so the
-- Single Static Message architecture survives restarts across all hosts.
-- Idempotent: safe to run multiple times.
-- ============================================================================

CREATE TABLE IF NOT EXISTS bd_settings (
    key         TEXT            PRIMARY KEY,
    value       TEXT,
    updated_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

ALTER TABLE bd_settings ENABLE ROW LEVEL SECURITY;

-- Optional seed key (null until first leaderboard post)
INSERT INTO bd_settings (key, value)
VALUES ('leaderboard_message_id', NULL)
ON CONFLICT (key) DO NOTHING;
