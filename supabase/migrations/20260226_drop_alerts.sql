-- Migration: Drop alerts + followed categories for personalized onboarding
-- Date: 2026-02-26

-- ============================================================================
-- 1. user_drop_alerts — subscribe to be notified before an event/drop
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_drop_alerts (
    user_id              UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    event_id             UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    notify_before_hours  INT NOT NULL DEFAULT 24,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, event_id)
);

-- RLS: users can only see/manage their own drop alerts
ALTER TABLE user_drop_alerts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_own_drop_alerts_select"
    ON user_drop_alerts FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "users_own_drop_alerts_insert"
    ON user_drop_alerts FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "users_own_drop_alerts_delete"
    ON user_drop_alerts FOR DELETE
    USING (auth.uid() = user_id);

-- Index for looking up alerts by event (e.g. when sending notifications)
CREATE INDEX IF NOT EXISTS idx_user_drop_alerts_event_id
    ON user_drop_alerts (event_id);

-- Index for listing a user's drop alerts
CREATE INDEX IF NOT EXISTS idx_user_drop_alerts_user_id
    ON user_drop_alerts (user_id);


-- ============================================================================
-- 2. Add followed_categories to user_settings for personalized onboarding
-- ============================================================================

-- Add the column if it doesn't exist (safe for re-runs)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_settings' AND column_name = 'followed_categories'
    ) THEN
        ALTER TABLE user_settings
            ADD COLUMN followed_categories TEXT[] DEFAULT '{}';
    END IF;
END $$;

-- Index for querying users by followed categories
CREATE INDEX IF NOT EXISTS idx_user_settings_followed_categories
    ON user_settings USING GIN (followed_categories);
