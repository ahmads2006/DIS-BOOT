-- ============================================================================
-- ByteDaily Migration 009: Make preferred_language nullable in bd_users
-- ============================================================================
-- Allows automatic role-based language detection fallback when no explicit
-- preference is set by the user.
-- Idempotent: safe to run multiple times.
-- ============================================================================

ALTER TABLE bd_users
    ALTER COLUMN preferred_language DROP NOT NULL,
    ALTER COLUMN preferred_language SET DEFAULT NULL;
