-- Data moat tables: supply tracking, verified sales, demand signals
-- Supports items 14-17 of the system improvements roadmap

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- Item 14: Supply snapshots — track listing counts over time for scarcity
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.supply_snapshots (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  category      text        NOT NULL,
  item_key      text        NOT NULL,
  source        text        NOT NULL DEFAULT 'firecrawl',
  listing_count int         NOT NULL DEFAULT 0 CHECK (listing_count >= 0),
  avg_price_eur numeric(12,2),
  min_price_eur numeric(12,2),
  max_price_eur numeric(12,2),
  snapshot_at   timestamptz NOT NULL DEFAULT now(),
  metadata      jsonb       DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_supply_snapshots_item
  ON public.supply_snapshots(category, item_key, snapshot_at DESC);

CREATE INDEX IF NOT EXISTS idx_supply_snapshots_category_time
  ON public.supply_snapshots(category, snapshot_at DESC);

COMMENT ON TABLE public.supply_snapshots
  IS 'Point-in-time supply counts per item/category from market crawls — feeds scarcity scoring';

-- RLS: service role only (backend writes, no user access)
ALTER TABLE public.supply_snapshots ENABLE ROW LEVEL SECURITY;

CREATE POLICY supply_snapshots_service_only ON public.supply_snapshots
  FOR ALL USING (false);

-- ─────────────────────────────────────────────────────────────────────────────
-- Item 16: Verified sales — ground-truth sale prices from user confirmations
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.verified_sales (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  item_id       uuid        NOT NULL REFERENCES public.items(id) ON DELETE CASCADE,
  user_id       uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  category      text        NOT NULL,
  sale_price    numeric(12,2) NOT NULL CHECK (sale_price > 0),
  currency      text        NOT NULL DEFAULT 'EUR'
                CHECK (currency IN ('EUR', 'USD', 'GBP', 'JPY')),
  platform      text,
  condition     text,
  sold_at       timestamptz,
  verified      boolean     NOT NULL DEFAULT false,
  notes         text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_verified_sales_item
  ON public.verified_sales(item_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_verified_sales_category
  ON public.verified_sales(category, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_verified_sales_user
  ON public.verified_sales(user_id);

COMMENT ON TABLE public.verified_sales
  IS 'User-reported sale prices — high-quality ground truth for ML training with 2x weight';

ALTER TABLE public.verified_sales ENABLE ROW LEVEL SECURITY;

CREATE POLICY verified_sales_own ON public.verified_sales
  FOR ALL USING (user_id = auth.uid());

-- ─────────────────────────────────────────────────────────────────────────────
-- Item 17: Demand signals — track search/mandate frequency per item/category
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.demand_signals (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  signal_type   text        NOT NULL CHECK (signal_type IN (
                              'mandate_created', 'search_query', 'item_viewed',
                              'price_alert_set', 'watchlist_add'
                            )),
  category      text,
  item_key      text,
  query_text    text,
  user_id       uuid,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_demand_signals_category_time
  ON public.demand_signals(category, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_demand_signals_type_time
  ON public.demand_signals(signal_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_demand_signals_item
  ON public.demand_signals(item_key, created_at DESC)
  WHERE item_key IS NOT NULL;

COMMENT ON TABLE public.demand_signals
  IS 'Aggregate demand signals from user actions — feeds trending/hot-item scoring';

ALTER TABLE public.demand_signals ENABLE ROW LEVEL SECURITY;

CREATE POLICY demand_signals_service_only ON public.demand_signals
  FOR ALL USING (false);

-- ─────────────────────────────────────────────────────────────────────────────
-- Materialized view: supply trend (7-day rolling average per item)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE MATERIALIZED VIEW IF NOT EXISTS public.mv_supply_trend AS
SELECT
  category,
  item_key,
  date_trunc('day', snapshot_at)::date AS snap_date,
  avg(listing_count)::int              AS avg_listings,
  avg(avg_price_eur)::numeric(12,2)    AS avg_price,
  count(*)                             AS sample_count
FROM public.supply_snapshots
WHERE snapshot_at > now() - interval '90 days'
GROUP BY category, item_key, date_trunc('day', snapshot_at)
ORDER BY category, item_key, snap_date DESC;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_supply_trend_pk
  ON public.mv_supply_trend(category, item_key, snap_date);

-- ─────────────────────────────────────────────────────────────────────────────
-- Materialized view: demand heat (top trending items in last 7 days)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE MATERIALIZED VIEW IF NOT EXISTS public.mv_demand_heat AS
SELECT
  coalesce(category, 'unknown') AS category,
  coalesce(item_key, query_text, 'general') AS item_key,
  signal_type,
  count(*) AS signal_count,
  count(DISTINCT user_id) AS unique_users,
  max(created_at) AS last_signal_at
FROM public.demand_signals
WHERE created_at > now() - interval '7 days'
GROUP BY coalesce(category, 'unknown'),
         coalesce(item_key, query_text, 'general'),
         signal_type
HAVING count(*) >= 2
ORDER BY signal_count DESC;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_demand_heat_pk
  ON public.mv_demand_heat(category, item_key, signal_type);

COMMIT;
