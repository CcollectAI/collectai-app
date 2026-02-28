-- ============================================================
-- Watchlist Monitor — columns for market price tracking
-- ============================================================

-- New columns on watchlist_items for the watchlist_monitor_worker
ALTER TABLE public.watchlist_items
  ADD COLUMN IF NOT EXISTS last_market_price NUMERIC,
  ADD COLUMN IF NOT EXISTS last_checked_at   TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS price_trend       TEXT CHECK (price_trend IN ('up', 'down', 'stable')),
  ADD COLUMN IF NOT EXISTS market_hit_count  INT DEFAULT 0;

-- Index for worker polling: oldest-checked items first
CREATE INDEX IF NOT EXISTS idx_watchlist_items_last_checked
  ON public.watchlist_items (last_checked_at ASC NULLS FIRST);
