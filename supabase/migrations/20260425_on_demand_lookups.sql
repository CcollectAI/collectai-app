-- 2026-04-25: cache table for on-demand paid-scraper enrichment.
-- When a user views/saves an item in a thin category, backend fires one
-- Scrape.do/SerpAPI call to fetch fresh comps. The result is cached here
-- so repeat lookups within TTL skip the paid call.
--
-- Row lifecycle: insert on first paid lookup; updated on each refresh;
-- never deleted (history is small + useful for spend audits).

CREATE TABLE IF NOT EXISTS public.on_demand_lookups (
    item_ref         text PRIMARY KEY,
    category         text NOT NULL,
    last_fetched_at  timestamptz NOT NULL DEFAULT now(),
    fetch_count      integer NOT NULL DEFAULT 1,
    hit_count        integer NOT NULL DEFAULT 0,
    cost_cents       integer NOT NULL DEFAULT 0,
    last_provider    text,
    last_error       text
);

CREATE INDEX IF NOT EXISTS idx_on_demand_lookups_fetched
  ON public.on_demand_lookups (last_fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_on_demand_lookups_category
  ON public.on_demand_lookups (category, last_fetched_at DESC);

ALTER TABLE public.on_demand_lookups ENABLE ROW LEVEL SECURITY;
CREATE POLICY on_demand_lookups_deny_all ON public.on_demand_lookups
  FOR ALL USING (false) WITH CHECK (false);
