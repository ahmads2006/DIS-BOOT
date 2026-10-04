-- ============================================================================
-- ByteDaily Migration 005: Add ends_at for adjustable poll duration
-- ============================================================================
-- Enables /bytedaily-extend and /bytedaily-reduce by storing an explicit
-- close timestamp instead of deriving it only from opened_at + fixed window.
-- Idempotent: safe to run multiple times.
-- ============================================================================

ALTER TABLE bd_polls
    ADD COLUMN IF NOT EXISTS ends_at TIMESTAMPTZ;

-- Backfill existing rows (12-hour default window from opened_at)
UPDATE bd_polls
SET ends_at = opened_at + INTERVAL '12 hours'
WHERE ends_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_bd_polls_ends_at
    ON bd_polls (ends_at);
