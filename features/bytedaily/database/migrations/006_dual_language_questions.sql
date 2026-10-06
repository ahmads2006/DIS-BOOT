-- ============================================================================
-- ByteDaily Migration 006: Add dual-language (English) columns to bd_questions
-- ============================================================================
-- Adds support for storing English translations of questions, options, and explanations.
-- Idempotent: safe to run multiple times.
-- ============================================================================

ALTER TABLE bd_questions
    ADD COLUMN IF NOT EXISTS question_en TEXT,
    ADD COLUMN IF NOT EXISTS options_en JSONB,
    ADD COLUMN IF NOT EXISTS choice_a_en TEXT,
    ADD COLUMN IF NOT EXISTS choice_b_en TEXT,
    ADD COLUMN IF NOT EXISTS choice_c_en TEXT,
    ADD COLUMN IF NOT EXISTS choice_d_en TEXT,
    ADD COLUMN IF NOT EXISTS explanation_en TEXT;
