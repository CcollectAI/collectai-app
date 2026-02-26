-- User privacy settings table
-- Used by Settings screen to persist privacy toggle preferences
CREATE TABLE IF NOT EXISTS user_privacy_settings (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    show_collection_value BOOLEAN NOT NULL DEFAULT true,
    show_item_count BOOLEAN NOT NULL DEFAULT true,
    allow_discovery BOOLEAN NOT NULL DEFAULT true,
    show_online_status BOOLEAN NOT NULL DEFAULT false,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- RLS: users can only read/write their own row
ALTER TABLE user_privacy_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own privacy settings"
    ON user_privacy_settings FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own privacy settings"
    ON user_privacy_settings FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own privacy settings"
    ON user_privacy_settings FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);
