-- 20260212_performance_indexes_and_user_settings.sql
-- R15-6: Additional performance indexes
-- R15-3: User settings for geo-aware currency/region

-- 1. Alert trigger history: composite for filtering by trigger type
CREATE INDEX IF NOT EXISTS idx_alert_history_user_type
    ON public.alert_trigger_history (user_id, trigger_type, created_at DESC);

-- 2. Item provenance: composite for user + event_type queries
CREATE INDEX IF NOT EXISTS idx_provenance_user_type
    ON public.item_provenance_events (user_id, event_type, created_at DESC);

-- 3. User settings table for currency, region, locale preferences
CREATE TABLE IF NOT EXISTS public.user_settings (
    user_id    UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    currency   TEXT NOT NULL DEFAULT 'EUR' CHECK (currency IN ('EUR','USD','JPY','GBP')),
    region     TEXT NOT NULL DEFAULT 'europe' CHECK (region IN ('americas','europe','japan','other')),
    locale     TEXT NOT NULL DEFAULT 'de-DE' CHECK (locale IN ('en-US','de-DE','ja-JP','nl-NL')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- RLS: users can only read/write their own settings
ALTER TABLE public.user_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_settings_select ON public.user_settings
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY user_settings_insert ON public.user_settings
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY user_settings_update ON public.user_settings
    FOR UPDATE USING (auth.uid() = user_id);

-- Auto-update updated_at on change
CREATE OR REPLACE FUNCTION public.update_user_settings_ts()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_user_settings_updated
    BEFORE UPDATE ON public.user_settings
    FOR EACH ROW EXECUTE FUNCTION public.update_user_settings_ts();
