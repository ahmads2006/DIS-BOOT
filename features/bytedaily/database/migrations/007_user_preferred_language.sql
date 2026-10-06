-- ============================================================================
-- ByteDaily Migration 007: Add preferred_language to bd_users
-- ============================================================================
-- Stores user language preference ('ar' or 'en') for bilingual ByteDaily interactions.
-- Idempotent: safe to run multiple times.
-- ============================================================================

ALTER TABLE bd_users
    ADD COLUMN IF NOT EXISTS preferred_language VARCHAR(5) NOT NULL DEFAULT 'ar';
