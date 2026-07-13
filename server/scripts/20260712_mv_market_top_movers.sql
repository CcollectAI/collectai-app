-- 2026-07-12 Market Movers DB object (feature: feat(market-movers), commit a3126b0).
-- APPLIED LIVE via DB_DSN_DIRECT (not the migration runner) — this file is the
-- source-of-truth record. Read by GET /catalog/top-movers
-- (catalog_browser_router.py). Rebuilt on the live market_hits_daily rollup
-- (text item_ref), NOT the dead item_metadata/v_item_price_daily_90d UUID chain.
-- See project_2026_07_12_top_movers_scope.

DROP MATERIALIZED VIEW IF EXISTS public.mv_market_top_movers;

CREATE MATERIALIZED VIEW public.mv_market_top_movers AS
WITH daily AS (
  SELECT item_ref, day, median_price, comps_count
  FROM public.market_hits_daily
  WHERE day >= current_date - 30
    AND median_price IS NOT NULL AND median_price > 0
),
agg AS (
  SELECT
    item_ref,
    max(day)                                                         AS last_day,
    (array_agg(median_price ORDER BY day DESC))[1]                   AS last_price,
    -- ::numeric so the guard + write + any CHECK compare in the same space
    -- (percentile_cont returns float8) — see learning_guard_must_match_constraint_type_space.
    (percentile_cont(0.5) WITHIN GROUP (ORDER BY median_price)
       FILTER (WHERE day >= current_date - 7))::numeric              AS med_7d,
    (percentile_cont(0.5) WITHIN GROUP (ORDER BY median_price))::numeric AS med_30d,
    sum(comps_count)                                                 AS comps_30d,
    count(DISTINCT day)                                              AS days_30d
  FROM daily
  GROUP BY item_ref
),
eligible AS (
  -- credibility floors (median-over-N philosophy): enough comps, real price,
  -- multiple days, recent activity, and exclude >500% swings as data glitches.
  SELECT *
  FROM agg
  WHERE comps_30d >= 5
    AND med_30d   >= 1
    AND days_30d  >= 3
    AND last_day  >= current_date - 7
    AND med_7d IS NOT NULL
    AND abs((last_price - med_30d) / med_30d) <= 5.0
)
SELECT
  e.item_ref,
  COALESCE(ci.category, split_part(e.item_ref, ':', 1))             AS category,
  ci.item_key,
  ci.title,
  ci.brand,
  ci.set_code,
  ci.rarity,
  ci.image_url,
  e.last_day,
  e.last_price,
  e.med_7d,
  e.med_30d,
  e.comps_30d,
  e.days_30d,
  round(((e.last_price - e.med_7d)  / e.med_7d)  * 100, 2)          AS delta_pct_7d,
  round(((e.last_price - e.med_30d) / e.med_30d) * 100, 2)          AS delta_pct_30d,
  (ci.item_key IS NOT NULL)                                         AS in_catalog
FROM eligible e
LEFT JOIN public.category_items ci
  ON (ci.category || ':' || ci.item_key) = e.item_ref;

-- unique key (for REFRESH ... CONCURRENTLY)
CREATE UNIQUE INDEX uq_mv_market_top_movers_item_ref
  ON public.mv_market_top_movers (item_ref);
-- API's gainers/losers-by-category read path
CREATE INDEX idx_mv_market_top_movers_d30 ON public.mv_market_top_movers (delta_pct_30d);
CREATE INDEX idx_mv_market_top_movers_cat ON public.mv_market_top_movers (category);

ANALYZE public.mv_market_top_movers;

-- Nightly refresh (pg_cron), after the market_hits_daily rollup (cron 39 @ 00:45 UTC).
--   SELECT cron.schedule('refresh-mv-market-top-movers','0 1 * * *',
--     'refresh materialized view concurrently public.mv_market_top_movers');  -- jobid 41
