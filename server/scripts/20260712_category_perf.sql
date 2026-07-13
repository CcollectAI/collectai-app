-- 2026-07-12 category-page perf DB objects.
-- APPLIED LIVE via DB_DSN_DIRECT (not the migration runner) — this file is the
-- source-of-truth record. Diagnosis: the collections/set surfaces were NOT slow
-- queries (10-40ms warm) — they were cold-buffer first-hits (1.6-2.1s) on
-- category_items. See project_2026_07_12_category_perf_and_theme_ingress.

-- 1) Localize the set-detail grid so it index-scans the set instead of scanning
--    the whole category (was: Rows Removed by Filter: ~19932 to find 304).
--    EXPLAIN cost 11130 -> 164; category_items blocks 3013 -> 55.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_category_items_category_set_code
  ON public.category_items (category, set_code);

-- 2) Pre-aggregate the "Browse by Set/Brand" rail so the endpoint is a tiny
--    indexed read (<60ms, 13 buffers) instead of a live 20K-row GROUP BY
--    (1.6-2.1s cold, 3013 buffers). Mirrors mv_catalog_item_price.
--    browse_catalog_collections (catalog_browser_router.py) reads this.
DROP MATERIALIZED VIEW IF EXISTS public.mv_catalog_collections;
CREATE MATERIALIZED VIEW public.mv_catalog_collections AS
  SELECT category, 'set'::text AS dim, set_code AS grp,
         COUNT(*) AS total_items,
         (ARRAY_AGG(image_url) FILTER (WHERE image_url IS NOT NULL AND image_url <> ''))[1] AS cover_image
  FROM public.category_items
  WHERE set_code IS NOT NULL AND set_code <> ''
  GROUP BY category, set_code
  UNION ALL
  SELECT category, 'brand'::text AS dim, brand AS grp,
         COUNT(*) AS total_items,
         (ARRAY_AGG(image_url) FILTER (WHERE image_url IS NOT NULL AND image_url <> ''))[1] AS cover_image
  FROM public.category_items
  WHERE brand IS NOT NULL AND brand <> ''
  GROUP BY category, brand;

CREATE UNIQUE INDEX uq_mv_catalog_collections ON public.mv_catalog_collections (category, dim, grp);
CREATE INDEX idx_mv_catalog_collections_read ON public.mv_catalog_collections (category, dim, total_items DESC);
ANALYZE public.mv_catalog_collections;

-- 3) Nightly refresh (pg_cron), after the catalog matview (cron 34 @ 00:00 UTC).
--    Applied via: SELECT cron.schedule('refresh-mv-catalog-collections','5 0 * * *',
--      'refresh materialized view concurrently public.mv_catalog_collections');  -- jobid 42
