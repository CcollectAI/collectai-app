-- Remember which catalogue items Discogs has nothing for (2026-09-27, Merle).
--
-- import_discogs re-selects every item without a fresh (7-day) discogs row, and
-- an item Discogs cannot match NEVER gets a row — so it was searched again every
-- day, forever. Measured on the 09-27 run: anime_ost_vinyl 1,103 items probed,
-- 376 matched, 293 with a price; the other ~810 were re-searched daily at ~1
-- request/s against Discogs' rate limit. Same for items that match a release
-- nobody is selling (lowest_price empty).
--
-- A FAILED request (timeout, 429, 5xx) is never written here — only a real
-- answer: `no_match` (search returned nothing, rechecked after 30 days) or
-- `no_price` (release found, nothing for sale, rechecked after 14 days).
--
-- item_ref is `<category>:<item_key>`, the same value market_hits.item_ref uses.
--
-- Server-only: written and read by the bake worker over DB_DSN as the table
-- owner. RLS on with no client policies, so PostgREST exposes nothing — plus
-- the restrictive 2FA policy every RLS table carries (20260926b).

CREATE TABLE IF NOT EXISTS public.discogs_probe_misses (
  item_ref        text        PRIMARY KEY,
  reason          text        NOT NULL CHECK (reason IN ('no_match', 'no_price')),
  misses          integer     NOT NULL DEFAULT 1,
  last_probed_at  timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.discogs_probe_misses ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS mfa_required ON public.discogs_probe_misses;
CREATE POLICY mfa_required ON public.discogs_probe_misses AS RESTRICTIVE FOR ALL TO authenticated
  USING ((SELECT public.mfa_satisfied())) WITH CHECK ((SELECT public.mfa_satisfied()));

REVOKE ALL ON public.discogs_probe_misses FROM anon, authenticated;

COMMENT ON TABLE public.discogs_probe_misses IS
  'Catalogue items Discogs had no match / no price for, so import_discogs skips them until a recheck (20260927). Server-only.';
