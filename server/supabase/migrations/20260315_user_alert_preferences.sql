-- User alert preferences: per-user notification settings for price drops,
-- new listings, milestones, and price increases.
--
-- Apply via: psql $DB_DSN -f 20260315_user_alert_preferences.sql
-- Or via Supabase Dashboard → SQL Editor

CREATE TABLE IF NOT EXISTS user_alert_preferences (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    price_drop_enabled BOOLEAN DEFAULT true,
    price_drop_threshold NUMERIC(5,2) DEFAULT 10.0,
    new_listing_enabled BOOLEAN DEFAULT true,
    milestone_enabled BOOLEAN DEFAULT true,
    price_increase_enabled BOOLEAN DEFAULT false,
    price_increase_threshold NUMERIC(5,2) DEFAULT 15.0,
    frequency TEXT DEFAULT 'instant' CHECK (frequency IN ('instant', 'daily', 'weekly')),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- RLS: each user can only read/write their own preferences row
ALTER TABLE user_alert_preferences ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage own alert preferences"
    ON user_alert_preferences
    FOR ALL
    USING (auth.uid() = user_id);

-- Index not needed (PK on user_id already provides it)

-- Trigger to auto-update updated_at on modification
CREATE OR REPLACE FUNCTION update_alert_preferences_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_alert_preferences_updated_at
    BEFORE UPDATE ON user_alert_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_alert_preferences_updated_at();
