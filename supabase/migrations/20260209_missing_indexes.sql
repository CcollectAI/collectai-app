-- 20260209_missing_indexes.sql
-- Add missing indexes for high-traffic query patterns.
-- All CREATE INDEX IF NOT EXISTS so this is safe to re-run.

-- 1. items(user_id, category) composite — used by listItems, searchItems, portfolio
CREATE INDEX IF NOT EXISTS idx_items_user_category
    ON public.items (user_id, category);

-- 2. events.created_by — used by "my events" filter in events tab
CREATE INDEX IF NOT EXISTS idx_events_created_by
    ON public.events (created_by);

-- 3. events(category, start_date) — used by personalized feed ordering
CREATE INDEX IF NOT EXISTS idx_events_category_start_date
    ON public.events (category, start_date);

-- 4. market_hits(normalized_key, ended_at) — used by price guide lookups
CREATE INDEX IF NOT EXISTS idx_mh_normkey_ended
    ON public.market_hits (normalized_key, ended_at DESC);

-- 5. market_hits title trigram — used by fuzzy title search in market endpoints
--    Requires pg_trgm extension (already enabled in earlier migration 20251004_0003_trigram.sql)
CREATE INDEX IF NOT EXISTS idx_mh_title_trgm
    ON public.market_hits USING gin (title gin_trgm_ops);

-- 6. user_price_alerts.user_id — used by alerts worker and alerts feature router
CREATE INDEX IF NOT EXISTS idx_user_price_alerts_user_id
    ON public.user_price_alerts (user_id);

-- 7. price_predictions(item_id, asof DESC) — used by frontend JOINs to pick latest prediction
CREATE INDEX IF NOT EXISTS idx_pp_item_asof
    ON public.price_predictions (item_id, asof DESC);

-- 8. feedback(item_id) — used by calibration_compute JOIN
CREATE INDEX IF NOT EXISTS idx_feedback_item_id
    ON public.feedback (item_id);
