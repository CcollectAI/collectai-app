-- v_market_hits_canon: one LEFT JOIN instead of a correlated subquery per row.
--
-- `hourly_refresh_best_comp` (pg_cron job 16, `0 * * * *`,
-- `REFRESH MATERIALIZED VIEW CONCURRENTLY public.mv_item_best_comp_canon`) has
-- been FAILING 18 of every 24 runs since 2026-08-11 18:00 UTC with
-- "canceling statement due to statement timeout". Measured 2026-08-12:
--
--   succeeded runs : 116-120 s
--   failed runs    : 121 s   <- the DB statement_timeout is 120000 ms
--
-- It is not a stall; the refresh simply grew into the timeout. It was 56.7 s
-- in the 2026-05-26 IO audit (docs/SUPABASE_IO_AUDIT_2026_05_26.md, job 16)
-- and measured 140.5 s today. The matview itself is 72 kB — all of the cost is
-- in the query behind it.
--
-- WHY IT IS SO EXPENSIVE. `mv_item_best_comp_canon` is a LATERAL per item:
--
--   FROM v_items_canon i JOIN LATERAL (
--     SELECT h2.id FROM v_market_hits_canon h2
--     WHERE h2.canonical_category = i.canonical_category
--     ORDER BY h2.id DESC LIMIT 1) h ON true
--
-- and `canonical_category` was computed by a CORRELATED SUBQUERY evaluated per
-- market_hits row:
--
--   COALESCE((SELECT m.canonical_category FROM category_map m
--             WHERE m.raw_category_lower = lower(mh.category)), lower(category))
--
-- There are 5 rows in v_items_canon and 1,444,719 in market_hits, and the
-- predicate is on a COMPUTED value so no index can serve it. That is 5 full
-- scans and ~7.2M correlated lookups per refresh, with no time filter at all.
--
-- THE FIX HERE. `category_map.raw_category_lower` is the PRIMARY KEY
-- (category_map_pkey, 72 rows / 72 distinct), so the scalar subquery returns at
-- most one row and a LEFT JOIN is exactly equivalent — it cannot duplicate
-- rows. The planner then hash-joins 72 rows once instead of probing per row.
--
--   before  140.5 s
--   after    68.2 s     (measured on the live DB, same LATERAL shape)
--
-- CREATE OR REPLACE (not DROP/CREATE) is deliberate: the view has SEVEN
-- dependents — mv_daily_median_price (pg_cron job 17), mv_item_best_comp_canon,
-- v_item_best_comp_scored_v2, v_listing_velocity_14d, v_new_listings_radar,
-- v_price_bands_30d, v_under_median_hits_7d_v2 — and replacing in place keeps
-- every dependent and all grants intact. Column list, order and types are
-- unchanged, which is what CREATE OR REPLACE VIEW requires. Job 17 reads the
-- same view, so it gets the same relief.
--
-- THIS IS RELIEF, NOT THE CURE. 68 s against a 120 s timeout is a 43% margin on
-- a table that grew 56.7 s -> 140.5 s in under three months. The durable fix is
-- to stop scanning market_hits once per item: aggregate it ONCE, which measured
-- 5.7 s (~25x) with an EXCEPT diff of 0 rows in BOTH directions against the
-- current definition. That requires recreating mv_item_best_comp_canon, whose
-- 3 dependents carry 96 grants between them, so it is written up as a separate
-- step rather than smuggled into this one. See docs/SUPABASE_IO_AUDIT_2026_05_26.md.
--
-- No index added: governance rule 1 in docs/DATA_SCALING_PLAN.md is "default =
-- refuse to add", and this plan does not need one.

CREATE OR REPLACE VIEW public.v_market_hits_canon AS
SELECT
    mh.id,
    mh.category,
    COALESCE(m.canonical_category, lower(mh.category)) AS canonical_category
FROM market_hits mh
LEFT JOIN category_map m ON m.raw_category_lower = lower(mh.category)
WHERE mh.category IS NOT NULL
  AND btrim(mh.category) <> ''::text;
