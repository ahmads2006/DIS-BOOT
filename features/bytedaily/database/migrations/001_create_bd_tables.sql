-- ============================================================================
-- ByteDaily Migration 001: Create all bd_ tables, indexes, RLS, and RPC
-- ============================================================================
-- Target: Supabase PostgreSQL (run in SQL Editor)
-- Idempotent: safe to run multiple times (IF NOT EXISTS / CREATE OR REPLACE)
-- RLS: enabled on all tables, but NO policies defined — add before production
-- ============================================================================

-- ─────────────────────────────────────────────
-- 1. bd_questions — question bank
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bd_questions (
    id              BIGSERIAL       PRIMARY KEY,
    question_text   TEXT            NOT NULL,
    choice_a        TEXT            NOT NULL,
    choice_b        TEXT            NOT NULL,
    choice_c        TEXT            NOT NULL,
    choice_d        TEXT            NOT NULL,
    correct_answer  CHAR(1)         NOT NULL CHECK (correct_answer IN ('A','B','C','D')),
    explanation     TEXT            NOT NULL DEFAULT '',
    difficulty      SMALLINT        NOT NULL DEFAULT 1 CHECK (difficulty BETWEEN 1 AND 3),
    tags            TEXT[]          NOT NULL DEFAULT '{}',
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────
-- 2. bd_polls — each posted question instance
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bd_polls (
    id                  BIGSERIAL       PRIMARY KEY,
    question_id         BIGINT          NOT NULL REFERENCES bd_questions(id),
    channel_id          BIGINT          NOT NULL,
    message_id          BIGINT,             -- question embed message (set after posting)
    stats_message_id    BIGINT,             -- stats summary message (set after closing)
    status              TEXT            NOT NULL DEFAULT 'open'
                                        CHECK (status IN ('open','closed','deleted')),
    opened_at           TIMESTAMPTZ     NOT NULL DEFAULT now(),
    closed_at           TIMESTAMPTZ,
    deleted_at          TIMESTAMPTZ,
    total_answers       INT             NOT NULL DEFAULT 0,
    correct_count       INT             NOT NULL DEFAULT 0,
    wrong_count         INT             NOT NULL DEFAULT 0
);

-- ─────────────────────────────────────────────
-- 3. bd_answers — individual user answers
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bd_answers (
    id              BIGSERIAL       PRIMARY KEY,
    poll_id         BIGINT          NOT NULL REFERENCES bd_polls(id) ON DELETE CASCADE,
    user_id         BIGINT          NOT NULL,
    chosen_answer   CHAR(1)         NOT NULL CHECK (chosen_answer IN ('A','B','C','D')),
    is_correct      BOOLEAN         NOT NULL,
    answered_at     TIMESTAMPTZ     NOT NULL DEFAULT now(),

    UNIQUE (poll_id, user_id)       -- one answer per user per poll
);

-- ─────────────────────────────────────────────
-- 4. bd_users — accumulated user stats
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bd_users (
    user_id         BIGINT          PRIMARY KEY,
    total_points    INT             NOT NULL DEFAULT 0,
    correct_count   INT             NOT NULL DEFAULT 0,
    wrong_count     INT             NOT NULL DEFAULT 0,
    current_streak  INT             NOT NULL DEFAULT 0,
    best_streak     INT             NOT NULL DEFAULT 0,
    last_poll_id    BIGINT,             -- tracks which poll they last answered
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────
-- Indexes
-- ─────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_bd_polls_status
    ON bd_polls (status);

CREATE INDEX IF NOT EXISTS idx_bd_polls_opened_at
    ON bd_polls (opened_at DESC);

CREATE INDEX IF NOT EXISTS idx_bd_answers_poll_id
    ON bd_answers (poll_id);

CREATE INDEX IF NOT EXISTS idx_bd_answers_user_id
    ON bd_answers (user_id);

CREATE INDEX IF NOT EXISTS idx_bd_users_total_points
    ON bd_users (total_points DESC);

CREATE INDEX IF NOT EXISTS idx_bd_questions_active
    ON bd_questions (is_active) WHERE is_active = TRUE;

-- ─────────────────────────────────────────────
-- Enable Row Level Security (no policies yet)
-- ─────────────────────────────────────────────
ALTER TABLE bd_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE bd_polls     ENABLE ROW LEVEL SECURITY;
ALTER TABLE bd_answers   ENABLE ROW LEVEL SECURITY;
ALTER TABLE bd_users     ENABLE ROW LEVEL SECURITY;

-- ─────────────────────────────────────────────
-- RPC: Atomic upsert for user stats after poll close
-- ─────────────────────────────────────────────
-- Called once per answering user when a poll transitions to 'closed'.
-- Handles streak logic atomically:
--   - correct answer → streak +1, best_streak = max(best_streak, new streak)
--   - wrong answer   → streak resets to 0, best_streak unchanged
--
CREATE OR REPLACE FUNCTION bd_upsert_user_stats(
    p_user_id       BIGINT,
    p_is_correct    BOOLEAN,
    p_points        INT,
    p_poll_id       BIGINT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO bd_users (
        user_id, total_points, correct_count, wrong_count,
        current_streak, best_streak, last_poll_id, updated_at
    )
    VALUES (
        p_user_id,
        p_points,
        CASE WHEN p_is_correct THEN 1 ELSE 0 END,
        CASE WHEN p_is_correct THEN 0 ELSE 1 END,
        CASE WHEN p_is_correct THEN 1 ELSE 0 END,
        CASE WHEN p_is_correct THEN 1 ELSE 0 END,
        p_poll_id,
        now()
    )
    ON CONFLICT (user_id) DO UPDATE SET
        total_points   = bd_users.total_points   + p_points,
        correct_count  = bd_users.correct_count  + CASE WHEN p_is_correct THEN 1 ELSE 0 END,
        wrong_count    = bd_users.wrong_count    + CASE WHEN p_is_correct THEN 0 ELSE 1 END,
        current_streak = CASE
                            WHEN p_is_correct THEN bd_users.current_streak + 1
                            ELSE 0
                         END,
        best_streak    = GREATEST(
                            bd_users.best_streak,
                            CASE WHEN p_is_correct
                                 THEN bd_users.current_streak + 1
                                 ELSE bd_users.best_streak
                            END
                         ),
        last_poll_id   = p_poll_id,
        updated_at     = now();
END;
$$;
