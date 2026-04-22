-- 2026-04-22: Watchlist router was broken against live schema — it targeted
-- the legacy `watchlist` table (bigint id, owner uuid, query, nk, est_value)
-- while `watchlist_items` (uuid id, user_id, title, target_price, …) is the
-- modern RLS-protected table. Rewriting the router to use watchlist_items
-- needs 4 columns the modern table didn't have.

ALTER TABLE public.watchlist_items
  ADD COLUMN IF NOT EXISTS item_id          text,
  ADD COLUMN IF NOT EXISTS predicted_value  numeric,
  ADD COLUMN IF NOT EXISTS price_trend      text,
  ADD COLUMN IF NOT EXISTS market_hit_count integer NOT NULL DEFAULT 0;
