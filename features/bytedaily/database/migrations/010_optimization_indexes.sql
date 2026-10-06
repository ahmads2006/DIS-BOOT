-- ============================================================================
-- ByteDaily Migration 010: Composite Performance & Query Optimization Indexes
-- ============================================================================
-- Idempotent: safe to run multiple times (IF NOT EXISTS)
-- ============================================================================

-- 1. Composite index for poll answers aggregation (total and correct counts)
CREATE INDEX IF NOT EXISTS idx_bd_answers_poll_correct
    ON bd_answers (poll_id, is_correct);

-- 2. Composite index for scheduler status and expiration lookups
CREATE INDEX IF NOT EXISTS idx_bd_polls_status_ends
    ON bd_polls (status, ends_at);

-- 3. Composite index for exam cooldown checks
CREATE TABLE IF NOT EXISTS exam_cooldowns (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    role_key VARCHAR(64) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_exam_cooldowns_user_role_exp
    ON exam_cooldowns (user_id, role_key, expires_at);

-- 4. Fast active questions retrieval for buffer queues
CREATE INDEX IF NOT EXISTS idx_bd_questions_active_id
    ON bd_questions (is_active, id);

-- 5. Streak leaderboard lookups
CREATE INDEX IF NOT EXISTS idx_bd_users_current_streak
    ON bd_users (current_streak DESC);
