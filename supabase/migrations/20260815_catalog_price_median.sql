-- Search showed EUR 697 for a watch the item page valued at EUR 41,978.
--
-- mv_catalog_item_price took ONE sample: `ORDER BY mh.seen_at DESC LIMIT 1` —
-- whatever market hit happened to be most recent. For a Rolex Day-Date 40 that
-- was a EUR 696.56 listing (a strap, a part, an aftermarket case; the market for
-- a EUR 42k watch is full of them) and that single row became THE price in
-- search AND in catalogue browse, which reads the same matview in four places
-- including the `sort=value` ranking.
--
-- search_router.py claimed price_eur "comes from mv_catalog_item_price — the
-- SAME source the catalog detail page reads", and argued at length that using a
-- different source would be bad: "a row that says EUR 12 in search and EUR 30
-- when tapped is worse than a row with no price". The intent was right, the
-- claim was false. The detail page computes a MEDIAN over 180 days of daily
-- rollups and only falls back to the latest comp when fewer than 3 comps back
-- it. One statistic per source is what allowed a 60x discrepancy.
--
-- This matches catalog_browser_router exactly: median-of-daily-medians over the
-- same 180-day window, from the same market_hits_daily rollup, with the same
-- >= 3 comps rule before the median is trusted.
--
-- Verified after applying, against the two items in the bug report:
--   Rolex Day-Date 40 Champagne (228238)  search 697 -> 41,978  (detail: 41,978)
--   Rolex Datejust 31mm Champagne          search      -> 16,429
DROP MATERIALIZED VIEW IF EXISTS public.mv_catalog_item_price;

CREATE MATERIALIZED VIEW public.mv_catalog_item_price AS
  SELECT ci.category,
         ci.item_key,
         mp.price_eur
    FROM category_items ci
    JOIN LATERAL (
      SELECT CASE
               WHEN COALESCE(SUM(d.comps_count), 0) >= 3
                    AND percentile_cont(0.5) WITHIN GROUP (ORDER BY d.median_price) IS NOT NULL
               THEN percentile_cont(0.5) WITHIN GROUP (ORDER BY d.median_price)
               ELSE (ARRAY_AGG(d.latest_price ORDER BY d.latest_seen_at DESC))[1]
             END AS price_eur
      FROM market_hits_daily d
      WHERE d.item_ref = ci.category || ':' || ci.item_key
        AND d.day > (CURRENT_DATE - 180)
        AND d.median_price IS NOT NULL
    ) mp ON mp.price_eur IS NOT NULL;

-- Required for REFRESH ... CONCURRENTLY; without it the nightly refresh takes
-- an ACCESS EXCLUSIVE lock and blocks every search for its duration.
CREATE UNIQUE INDEX mv_catalog_item_price_key
  ON public.mv_catalog_item_price (category, item_key);

REVOKE ALL ON public.mv_catalog_item_price FROM anon;
GRANT SELECT ON public.mv_catalog_item_price TO authenticated;
