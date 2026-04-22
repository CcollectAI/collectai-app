-- 2026-04-22: easy column adds surfaced by the SQL-drift audit.
-- Each column was already referenced by router code; the table just
-- never had the column created.

-- ---------------------------------------------------------------------------
-- 1. profiles: display_name, avatar_url, avatar_color
--    Used by gamification_router leaderboard JOIN and likely v_chat_inbox_v1
--    once we promote display_name over the bare username fallback.
-- ---------------------------------------------------------------------------
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS display_name text,
  ADD COLUMN IF NOT EXISTS avatar_url   text,
  ADD COLUMN IF NOT EXISTS avatar_color text;

-- ---------------------------------------------------------------------------
-- 2. events.sponsor_company_id
--    Used by sponsor_company_router (list events for a sponsor) +
--    events_announcements (resolve sponsor display name). The events table
--    already has scalar sponsor_name/sponsor_tier columns, but no FK to
--    sponsor_companies.id — so dashboards can't filter "all events sponsored
--    by company X". Adding the FK column closes the loop.
-- ---------------------------------------------------------------------------
ALTER TABLE public.events
  ADD COLUMN IF NOT EXISTS sponsor_company_id uuid;

CREATE INDEX IF NOT EXISTS idx_events_sponsor_company_id
  ON public.events (sponsor_company_id)
  WHERE sponsor_company_id IS NOT NULL;

-- FK is nullable (most events are unsponsored). NOT VALID lets the migration
-- run cheaply on a populated events table; ALTER TABLE ... VALIDATE CONSTRAINT
-- can be run later once we're sure no orphan rows exist.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema = 'public'
      AND table_name = 'events'
      AND constraint_name = 'events_sponsor_company_id_fkey'
  ) THEN
    ALTER TABLE public.events
      ADD CONSTRAINT events_sponsor_company_id_fkey
      FOREIGN KEY (sponsor_company_id)
      REFERENCES public.sponsor_companies(id)
      ON DELETE SET NULL
      NOT VALID;
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 3. device_tokens.active
--    billing_router push-notification fan-out filters `WHERE dt.active = true`
--    so deactivated tokens (e.g. after a DeviceNotRegistered push error) can
--    be skipped. Default true so existing rows are treated as live.
-- ---------------------------------------------------------------------------
ALTER TABLE public.device_tokens
  ADD COLUMN IF NOT EXISTS active boolean NOT NULL DEFAULT true;

CREATE INDEX IF NOT EXISTS idx_device_tokens_user_active
  ON public.device_tokens (user_id) WHERE active = true;
