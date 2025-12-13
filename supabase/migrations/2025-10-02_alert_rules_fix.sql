BEGIN;

-- Create table if missing
CREATE TABLE IF NOT EXISTS public.alert_rules (
  id           bigserial PRIMARY KEY,
  user_id      uuid NOT NULL,
  normalized_key text,
  category     text,
  spike_pct    numeric(5,2) DEFAULT 15.0,  -- p7 >= (1+spike_pct%) * p30
  drop_pct     numeric(5,2) DEFAULT 15.0,  -- p7 <= (1-drop_pct%) * p30
  enabled      boolean      DEFAULT true,
  created_at   timestamptz  DEFAULT now()
);

-- Expression-based UNIQUE constraint must be a UNIQUE INDEX (not table constraint)
CREATE UNIQUE INDEX IF NOT EXISTS ux_alert_rules_user_key_cat
ON public.alert_rules (
  user_id,
  (coalesce(normalized_key, '')),
  (coalesce(category, ''))
);

-- Optional: enable RLS without adding policies that need Supabase's auth.uid().
-- In local dev, you likely don't want to block access; skip policies here.
ALTER TABLE public.alert_rules ENABLE ROW LEVEL SECURITY;

COMMIT;
