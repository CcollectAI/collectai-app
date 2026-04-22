-- 2026-04-22: 3 missing columns surfaced by bake.log runtime errors during
-- the schema E2E audit. Each had inline comments admitting it was broken
-- but the fix was never landed.

-- 1. user_settings.notification_preferences (jsonb)
--    Used by notification_router.update_notification_preferences (UPSERT) +
--    value_change_worker (read for digest gating). Existing inline comments
--    in both files note the column was missing.
ALTER TABLE public.user_settings
  ADD COLUMN IF NOT EXISTS notification_preferences jsonb NOT NULL DEFAULT '{}'::jsonb;

-- 2. user_settings.subscription_tier (text)
--    Used by app/lib/notify.py + workers/value_change_worker for plan-based
--    notification gating ('free' / 'pro' / 'premium').
ALTER TABLE public.user_settings
  ADD COLUMN IF NOT EXISTS subscription_tier text;
COMMENT ON COLUMN public.user_settings.subscription_tier IS
  'NULL = unset (treat as free). Set by Stripe webhook on subscription change.';

-- 3. events.franchise_id (text)
--    Used by pipelines/event_enrich.py to tag events with a franchise (e.g.
--    "pokemon", "starwars", "lego"). Errored every event-scraper cycle since
--    franchise tagging was added — events kept landing with NULL franchise.
ALTER TABLE public.events
  ADD COLUMN IF NOT EXISTS franchise_id text;
CREATE INDEX IF NOT EXISTS idx_events_franchise_id
  ON public.events (franchise_id)
  WHERE franchise_id IS NOT NULL;
