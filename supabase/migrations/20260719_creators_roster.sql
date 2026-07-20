-- Creator roster — the micro-influencers in the growth program.
--
-- This is the app-repo-owned definition of `creators`. The admin dashboard
-- template also defines it (collectai-admin/supabase/migrations/001_kpi_tables.sql
-- + the ALTERs in 002_shopify_enhanced_kpis.sql), but running those wholesale
-- would also create `orders` and `kpi_events` — two very generically named
-- tables that nothing reads: the creator leaderboard was repointed to
-- profiles.referred_by_code and subscription_events. Both admin files use
-- CREATE TABLE IF NOT EXISTS / ADD COLUMN IF NOT EXISTS, so they remain safe
-- no-ops against this table if they are ever run.
--
-- Columns match the admin dashboard's expectations exactly (src/lib/kpi.ts
-- fetchCreatorLeaderboard and src/app/api/creators/route.ts).

CREATE TABLE IF NOT EXISTS public.creators (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name                 TEXT NOT NULL,
  handle               TEXT NOT NULL,
  platform             TEXT NOT NULL DEFAULT 'tiktok',
  language             TEXT NOT NULL DEFAULT 'en',
  -- Soft-referenced by profiles.referred_by_code and
  -- subscription_events.affiliate_code. Stored upper-case; signup, the
  -- handle_new_user trigger and the admin write route all normalise to match.
  affiliate_code       TEXT UNIQUE NOT NULL,
  is_active            BOOLEAN NOT NULL DEFAULT TRUE,
  -- What this creator costs: seeded units seeded and the commission rate.
  kits_sent            INT NOT NULL DEFAULT 2,
  cogs_per_kit_cents   INT NOT NULL DEFAULT 600,
  affiliate_payout_pct NUMERIC(5,2) NOT NULL DEFAULT 15.00,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Added separately so this file is a no-op when the admin template's 001/002
-- created the table first (those omit some of these).
ALTER TABLE public.creators ADD COLUMN IF NOT EXISTS kits_sent INT NOT NULL DEFAULT 2;
ALTER TABLE public.creators ADD COLUMN IF NOT EXISTS cogs_per_kit_cents INT NOT NULL DEFAULT 600;
ALTER TABLE public.creators ADD COLUMN IF NOT EXISTS affiliate_payout_pct NUMERIC(5,2) NOT NULL DEFAULT 15.00;

CREATE INDEX IF NOT EXISTS idx_creators_active
  ON public.creators (is_active) WHERE is_active;

-- ─── RLS ────────────────────────────────────────────────────────────────────
-- Read-only for anon: the admin dashboard reads the roster with the public
-- anon key. Writes deliberately have NO policy — they go through
-- /api/creators, which uses the service-role key behind the admin session
-- cookie. Adding an anon write policy here would let anyone holding the public
-- anon key rewrite the roster and therefore the payout basis.

ALTER TABLE public.creators ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS creators_read ON public.creators;
CREATE POLICY creators_read ON public.creators FOR SELECT USING (TRUE);
