-- Catalogue size per category, materialised.
--
-- `v_category_summaries_v1` recomputed this on EVERY request: a full aggregate
-- over 225,737 category_items rows to produce 55 numbers that are identical for
-- every member in the world. Warm it cost ~108ms; cold, ~7.6s, which is what a
-- member feels when they open Analytics after not using the app for a while.
--
-- Measured on prod 2026-08-14, after the item_key index landed:
--   view via PostgREST: 7.58s cold, 0.59s / 0.47s warm
--   of which the totals aggregate alone: 413ms cold, 108ms warm in psql
--
-- Refreshed every 15 minutes alongside the other core matviews. The catalogue
-- changes when the miner or an ingest run adds rows, so a slightly stale total
-- is a completion percentage off by a fraction of a point — not a wrong answer
-- about what the member owns, which is the half that stays live.
CREATE MATERIALIZED VIEW IF NOT EXISTS public.mv_category_totals AS
  SELECT ci.category, count(DISTINCT ci.id) AS total_count
  FROM public.category_items ci
  GROUP BY ci.category;

-- REFRESH ... CONCURRENTLY requires a unique index, and without it the refresh
-- takes an ACCESS EXCLUSIVE lock that blocks every reader for its duration.
CREATE UNIQUE INDEX IF NOT EXISTS mv_category_totals_category_key
  ON public.mv_category_totals (category);

COMMENT ON MATERIALIZED VIEW public.mv_category_totals IS
  'Per-category catalogue size. User-independent, refreshed every 15 minutes. '
  'Read by v_category_summaries_v1, which used to aggregate 225k rows per '
  'request to compute it.';

-- The DEFAULT PRIVILEGES trap this schema has: creating a relation hands
-- anon/authenticated a broad grant. Narrow it deliberately. `authenticated`
-- needs SELECT because v_category_summaries_v1 is security_invoker.
REVOKE ALL ON public.mv_category_totals FROM anon;
REVOKE ALL ON public.mv_category_totals FROM authenticated;
GRANT SELECT ON public.mv_category_totals TO authenticated;
