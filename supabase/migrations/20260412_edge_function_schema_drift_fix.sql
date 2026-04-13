-- Fix schema drift between Supabase edge functions and the live DB
-- Found by schema_drift_check on 2026-04-12
--
-- 1. predict_sessions: predict-complete/index.ts writes output + image_url
-- 2. label_events:     predict-label/index.ts writes source + version

-- ── predict_sessions ──────────────────────────────────────────────────
ALTER TABLE public.predict_sessions
  ADD COLUMN IF NOT EXISTS output    jsonb,
  ADD COLUMN IF NOT EXISTS image_url text;

-- ── label_events ──────────────────────────────────────────────────────
ALTER TABLE public.label_events
  ADD COLUMN IF NOT EXISTS source    text,
  ADD COLUMN IF NOT EXISTS version   text,
  ADD COLUMN IF NOT EXISTS image_url text;

-- ── PostgREST schema reload ───────────────────────────────────────────
NOTIFY pgrst, 'reload schema';
