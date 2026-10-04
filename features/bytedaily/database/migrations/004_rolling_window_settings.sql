-- ============================================================================
-- ByteDaily Migration 004: Rolling window message ID keys in bd_settings
-- ============================================================================
-- Tracks the two allowed challenge-channel bot messages:
--   current_question_message_id  → active pinned question embed
--   previous_result_message_id   → last poll's results embed (unpinned)
-- Idempotent: safe to run multiple times.
-- ============================================================================

INSERT INTO bd_settings (key, value)
VALUES
    ('current_question_message_id', NULL),
    ('previous_result_message_id', NULL)
ON CONFLICT (key) DO NOTHING;
