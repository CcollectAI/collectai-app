-- Performance indexes for alert dedup, item lookups, and catalog search

-- Alert trigger history: fast dedup lookups by user+item+type
CREATE INDEX IF NOT EXISTS idx_alert_trigger_history_user_item
    ON public.alert_trigger_history (user_id, item_id, trigger_type, created_at DESC);

-- Items: user's items filtered by category (portfolio, deepdive)
CREATE INDEX IF NOT EXISTS idx_items_user_category
    ON public.items (user_id, category);

-- Category items: category filter (exact match) + trigram for ILIKE '%query%'
CREATE INDEX IF NOT EXISTS idx_category_items_category
    ON public.category_items (category);

-- Enable pg_trgm extension if not already present (for ILIKE acceleration)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_category_items_title_trgm
    ON public.category_items USING gin (title gin_trgm_ops);
