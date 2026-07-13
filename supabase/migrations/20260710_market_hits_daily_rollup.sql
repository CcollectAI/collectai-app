-- market_hits_daily rollup — warm-tier for catalog pricing (2026-07-10)
--
-- WHY: catalog item pricing (GET /catalog/{cat}/items/{key}/price) read raw
-- market_hits over 180d for a median. market_hits is the largest partitioned
-- table (~1.8 GB/mo) and dropping its partitions (retention) truncated pricing.
-- This compact daily digest (one row per item/day: count, median, min/max,
-- latest) is ~7x smaller than the raw window and survives partition retention,
-- so market_hits raw can drop to 1 month while pricing keeps 180d of depth.
--
-- The reader (catalog_browser_router.get_catalog_item_price) computes the 180d
-- value as median-of-daily-medians (robust; negligible shift from
-- median-of-all-comps for a market-value display) and SUM(comps_count).
--
-- Deployed live 2026-07-10: table + 2.5M-row backfill + cron jobs 39/40.

CREATE TABLE IF NOT EXISTS public.market_hits_daily (
  item_ref        text NOT NULL,
  day             date NOT NULL,
  comps_count     integer NOT NULL,
  median_price    numeric,
  min_price       numeric,
  max_price       numeric,
  latest_price    numeric,
  latest_seen_at  timestamptz,
  PRIMARY KEY (item_ref, day)
);

-- Nightly rollup: re-roll the last 2 days from market_hits (idempotent upsert).
SELECT cron.schedule(
  'rollup-market-hits-daily',
  '45 0 * * *',
  $$
  INSERT INTO public.market_hits_daily
      (item_ref, day, comps_count, median_price, min_price, max_price, latest_price, latest_seen_at)
  SELECT item_ref, seen_at::date, count(*),
         percentile_cont(0.5) WITHIN GROUP (ORDER BY price_eur), min(price_eur), max(price_eur),
         (array_agg(price_eur ORDER BY seen_at DESC))[1], max(seen_at)
  FROM public.market_hits
  WHERE price_eur IS NOT NULL AND seen_at >= (current_date - interval '2 days')
  GROUP BY item_ref, seen_at::date
  ON CONFLICT (item_ref, day) DO UPDATE SET
      comps_count=EXCLUDED.comps_count, median_price=EXCLUDED.median_price,
      min_price=EXCLUDED.min_price, max_price=EXCLUDED.max_price,
      latest_price=EXCLUDED.latest_price, latest_seen_at=EXCLUDED.latest_seen_at
  $$
);

-- Retention on the rollup itself (400d — well past the 180d pricing window).
SELECT cron.schedule(
  'market-hits-daily-retention',
  '50 3 * * *',
  $$DELETE FROM public.market_hits_daily WHERE day < (current_date - interval '400 days')$$
);
