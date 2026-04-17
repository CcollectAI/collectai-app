-- Track when the marketplace scraper last ATTEMPTED an item, regardless
-- of whether it produced hits. Without this, the selector keeps picking
-- the same stalest NULL-last_seen items (niche anime_ost_vinyl / seiyuu
-- releases that no adapter finds) on every cycle — starving productive
-- items indefinitely.
--
-- Selection policy:
--   1. NULLs first (items never attempted — bootstrap)
--   2. Then oldest attempt (round-robin after bootstrap)
-- This caps each item's scrape frequency at ~catalog_size/batch_size cycles.
--
-- Separate from mh.last_seen (which tracks DATA, not ATTEMPTS). An item
-- can have last_seen=NULL forever but last_scrape_attempt_at recent, which
-- correctly means "we've tried, no luck, try again later".

ALTER TABLE public.category_items
  ADD COLUMN IF NOT EXISTS last_scrape_attempt_at timestamptz;

-- Partial index: only the "never attempted" subset needs fast lookup
-- (the ORDER BY for non-NULL is a table scan either way, and catalog is
-- ~140K rows so a plain index pays for itself only if the workload is
-- hot). NULLs-first bootstrap is the critical path.
CREATE INDEX IF NOT EXISTS idx_category_items_scrape_attempt_null
  ON public.category_items (last_scrape_attempt_at)
  WHERE last_scrape_attempt_at IS NULL;

-- PostgREST schema reload so any REST code can see the new column immediately
NOTIFY pgrst, 'reload schema';
