-- Migration 011: User Reminders preference for ByteDaily Streak System
ALTER TABLE bd_users ADD COLUMN IF NOT EXISTS reminder_enabled BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_bd_users_reminder ON bd_users(user_id) WHERE reminder_enabled IS TRUE;
