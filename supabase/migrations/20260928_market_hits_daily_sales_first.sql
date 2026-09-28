-- Daily rollup: SALES FIRST, asking prices only as a fallback (OPEN_DECISIONS #14, 2026-09-28).
--
-- The rollup medianed every priced row, listings included. Sales-only would have
-- emptied the daily price of 24,525 of 97,111 items priced in 30 d (the eBay-fed
-- categories have listings only — eBay sold data needs an API we do not have).
-- So: on an item-day that has sales, only the sales count; an item-day with no
-- sales still gets its listings' median. Measured: 1,237 of 1,650,911 item-days
-- change; no item loses its price.
--
-- pg_cron 1.6: cron.schedule() with an existing job name replaces its command.
SELECT cron.schedule(
  'rollup-market-hits-daily',
  '45 0 * * *',
  $$INSERT INTO public.market_hits_daily (item_ref, day, comps_count, median_price, min_price, max_price, latest_price, latest_seen_at)
    SELECT item_ref, d, count(*),
           percentile_cont(0.5) WITHIN GROUP (ORDER BY price_eur), min(price_eur), max(price_eur),
           (array_agg(price_eur ORDER BY seen_at DESC))[1], max(seen_at)
    FROM (
      SELECT item_ref, seen_at, seen_at::date AS d, price_eur, is_listing,
             bool_or(is_listing IS NOT TRUE) OVER (PARTITION BY item_ref, seen_at::date) AS day_has_sales
      FROM public.market_hits
      WHERE price_eur IS NOT NULL AND seen_at >= (current_date - interval '2 days')
    ) h
    WHERE is_listing IS NOT TRUE OR NOT day_has_sales
    GROUP BY item_ref, d
    ON CONFLICT (item_ref, day) DO UPDATE SET comps_count=EXCLUDED.comps_count, median_price=EXCLUDED.median_price,
      min_price=EXCLUDED.min_price, max_price=EXCLUDED.max_price, latest_price=EXCLUDED.latest_price,
      latest_seen_at=EXCLUDED.latest_seen_at$$
);
