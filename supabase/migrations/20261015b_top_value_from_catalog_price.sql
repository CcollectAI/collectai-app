-- "Most valuable" ranks by the price the catalogue SHOWS (2026-10-15).
--
-- Walked on Android: Yu-Gi-Oh "Most valuable" opened on Anotherverse Stratios,
-- True Exodia, Crocodile, Ghost Token, Ojama Token… while the catalogue's own
-- prices put 1st-edition Blue-Eyes / Dark Magician (LOB) and sealed booster
-- boxes at the top (EUR 1,380–2,760). Two definitions of "price":
--
--   mv_category_top_value   latest market_hits row per item_ref, last 180 days
--                           (market_hits retention is 2 months, so effectively
--                           ~60 days) — TCGplayer-keyed rows, whose feed
--                           (tcgcsv) has 403'd since 2026-08-01, can never rank
--   mv_catalog_item_price   180-day median of market_hits_daily — what the
--                           grid tile, catalogue page and search display
--
-- The grid tile even showed the first price (Anotherverse Stratios EUR 302.89)
-- while its catalogue page showed the second (EUR 245.92).
--
-- Now ranked from mv_catalog_item_price: one definition. Same columns and the
-- same unique index, so catalog_browser_router (`ORDER BY tv.rn`, reads
-- tv.price_eur) and the pg_cron job 'refresh-mv-category-top-value' (03:10 UTC,
-- CONCURRENTLY) keep working unchanged; mv_catalog_item_price refreshes at
-- 00:00, before it. `seen_at` is the item's latest market_hits_daily day.
--
-- Grants: SELECT only. The old view carried full privileges for anon and
-- authenticated (meaningless on a matview, but not what anyone meant); only
-- the API (owner) reads it.
DROP MATERIALIZED VIEW IF EXISTS public.mv_category_top_value;

CREATE MATERIALIZED VIEW public.mv_category_top_value AS
SELECT ranked.category,
       ranked.catalog_item_id,
       ranked.item_ref,
       ranked.price_eur,
       (SELECT max(d.day)::timestamptz FROM public.market_hits_daily d
         WHERE d.item_ref = ranked.item_ref) AS seen_at,
       ranked.rn
  FROM (
    SELECT mp.category,
           ci.id AS catalog_item_id,
           mp.category || ':' || mp.item_key AS item_ref,
           mp.price_eur,
           row_number() OVER (PARTITION BY mp.category ORDER BY mp.price_eur DESC, ci.id) AS rn
      FROM public.mv_catalog_item_price mp
      JOIN public.category_items ci
        ON ci.category = mp.category AND ci.item_key = mp.item_key
  ) ranked
 WHERE ranked.rn <= 60;

CREATE UNIQUE INDEX mv_category_top_value_cat_rn_uidx
  ON public.mv_category_top_value (category, rn);

REVOKE ALL ON public.mv_category_top_value FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.mv_category_top_value TO anon, authenticated, service_role, collector_bot;
ANALYZE public.mv_category_top_value;
