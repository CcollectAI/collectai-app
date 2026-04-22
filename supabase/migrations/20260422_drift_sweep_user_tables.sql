-- 2026-04-22: drift sweep batch 2 — two missing user-feature tables.

-- ---------------------------------------------------------------------------
-- 1. user_alert_preferences — read by GET /me/alert-preferences,
--    upserted by PATCH /me/alert-preferences in user_settings_router.
--    Schema and defaults derived from the router's SQL + DEFAULT_ALERT_PREFS.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.user_alert_preferences (
  user_id                    uuid PRIMARY KEY,
  price_drop_enabled         boolean    NOT NULL DEFAULT true,
  price_drop_threshold       integer    NOT NULL DEFAULT 10,   -- percent
  new_listing_enabled        boolean    NOT NULL DEFAULT true,
  milestone_enabled          boolean    NOT NULL DEFAULT true,
  price_increase_enabled     boolean    NOT NULL DEFAULT false,
  price_increase_threshold   integer    NOT NULL DEFAULT 20,   -- percent
  frequency                  text       NOT NULL DEFAULT 'daily',
  updated_at                 timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT user_alert_preferences_frequency_chk
    CHECK (frequency IN ('immediate', 'daily', 'weekly'))
);

ALTER TABLE public.user_alert_preferences ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'user_alert_preferences'
      AND policyname = 'user_alert_preferences_self_rw'
  ) THEN
    CREATE POLICY user_alert_preferences_self_rw ON public.user_alert_preferences
      USING (user_id = auth.uid())
      WITH CHECK (user_id = auth.uid());
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 2. scan_corrections — written + read by intake_feedback_router.
--    Tracks user-supplied corrections to QuickScan classifications so the
--    feedback loop can retrain when category corrections cross a threshold.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.scan_corrections (
  id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id               uuid        NOT NULL,
  scan_session_id       text        NOT NULL,
  corrected_name        text,
  corrected_category    text,
  corrected_condition   text,
  user_weight           numeric     NOT NULL DEFAULT 1.0,
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT scan_corrections_user_session_uniq UNIQUE (user_id, scan_session_id)
);

CREATE INDEX IF NOT EXISTS idx_scan_corrections_corrected_category
  ON public.scan_corrections (corrected_category)
  WHERE corrected_category IS NOT NULL;

ALTER TABLE public.scan_corrections ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'scan_corrections'
      AND policyname = 'scan_corrections_self_rw'
  ) THEN
    CREATE POLICY scan_corrections_self_rw ON public.scan_corrections
      USING (user_id = auth.uid())
      WITH CHECK (user_id = auth.uid());
  END IF;
END $$;
