-- ============================================================================
-- ByteDaily Migration 002: Performance indexes + question history
-- ============================================================================
-- Target: Supabase PostgreSQL (run in SQL Editor or via bot startup)
-- Idempotent: safe to run multiple times (IF NOT EXISTS)
-- ============================================================================

-- ─────────────────────────────────────────────
-- 1. High-performance indexes
-- ─────────────────────────────────────────────
-- Leaderboard ranking (ORDER BY total_points DESC)
CREATE INDEX IF NOT EXISTS idx_bd_users_points
    ON bd_users (total_points DESC);

-- Active poll lookups (WHERE status = …)
CREATE INDEX IF NOT EXISTS idx_bd_polls_status
    ON bd_polls (status);

-- Voting lookups (poll_id + user_id) — complements UNIQUE constraint
CREATE INDEX IF NOT EXISTS idx_bd_answers_poll_user
    ON bd_answers (poll_id, user_id);

-- ─────────────────────────────────────────────
-- 2. bd_question_history — prevent duplicate asks
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bd_question_history (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    question_id  BIGINT NOT NULL REFERENCES bd_questions(id),
    asked_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    poll_id      BIGINT REFERENCES bd_polls(id)
);

CREATE INDEX IF NOT EXISTS idx_bd_q_history_qid
    ON bd_question_history (question_id);

CREATE INDEX IF NOT EXISTS idx_bd_q_history_asked_at
    ON bd_question_history (asked_at DESC);

-- RLS (consistent with other bd_ tables; no policies yet)
ALTER TABLE bd_question_history ENABLE ROW LEVEL SECURITY;

-- ─────────────────────────────────────────────
-- 3. Seed history from existing polls (one-time backfill)
--    Avoids re-asking questions already posted before this migration.
-- ─────────────────────────────────────────────
INSERT INTO bd_question_history (question_id, asked_at, poll_id)
SELECT p.question_id, p.opened_at, p.id
FROM bd_polls p
WHERE NOT EXISTS (
    SELECT 1
    FROM bd_question_history h
    WHERE h.poll_id = p.id
);
