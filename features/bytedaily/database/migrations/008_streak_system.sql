-- ============================================================================
-- ByteDaily Migration 008: Streak system & milestone tracking in bd_users
-- ============================================================================
-- Ensures columns exist for tracking current streak, highest streak, and last answered poll.
-- Idempotent: safe to run multiple times.
-- ============================================================================

ALTER TABLE bd_users
    ADD COLUMN IF NOT EXISTS current_streak INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS highest_streak INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS best_streak INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS last_answered_poll_id BIGINT,
    ADD COLUMN IF NOT EXISTS last_poll_id BIGINT;

-- Backfill highest_streak from best_streak if best_streak exists and highest_streak is 0
UPDATE bd_users
SET highest_streak = best_streak
WHERE highest_streak = 0 AND best_streak > 0;

-- Backfill last_answered_poll_id from last_poll_id if last_answered_poll_id is null
UPDATE bd_users
SET last_answered_poll_id = last_poll_id
WHERE last_answered_poll_id IS NULL AND last_poll_id IS NOT NULL;
