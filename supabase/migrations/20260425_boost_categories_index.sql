-- 2026-04-25: support index for marketplace_scrape_scheduler BOOST pass.
-- The Pass-0 query in _get_stale_items filters category_items by
--   WHERE title IS NOT NULL AND category = ANY($2)
--   ORDER BY last_scrape_attempt_at ASC NULLS FIRST
-- and was hitting the pooler 30s cap repeatedly (10+ consecutive worker
-- errors 05:25 → 06:50 UTC today) because it had no index covering both
-- the category filter AND the NULLS-FIRST sort.
--
-- This composite index covers it cleanly. Partial on title to match the
-- existing partial-index pattern used elsewhere on this table.

CREATE INDEX IF NOT EXISTS idx_category_items_boost
  ON public.category_items (category, last_scrape_attempt_at NULLS FIRST)
  WHERE title IS NOT NULL;
