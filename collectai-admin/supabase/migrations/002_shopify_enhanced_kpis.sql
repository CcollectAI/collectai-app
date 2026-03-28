-- ============================================================================
-- Enhanced KPI tables: Shopify webhook support, advanced metrics
-- Run after 001_kpi_tables.sql
-- ============================================================================

-- Add new columns to orders for Shopify webhook data
ALTER TABLE orders ADD COLUMN IF NOT EXISTS line_items JSONB DEFAULT '[]';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS total_line_items INT NOT NULL DEFAULT 1;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS discount_codes JSONB DEFAULT '[]';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS landing_site TEXT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS referring_site TEXT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_id TEXT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS is_repeat_customer BOOLEAN DEFAULT FALSE;

-- Add COGS and affiliate payout to creators
ALTER TABLE creators ADD COLUMN IF NOT EXISTS kits_sent INT NOT NULL DEFAULT 2;
ALTER TABLE creators ADD COLUMN IF NOT EXISTS cogs_per_kit_cents INT NOT NULL DEFAULT 600;
ALTER TABLE creators ADD COLUMN IF NOT EXISTS affiliate_payout_pct NUMERIC(5,2) NOT NULL DEFAULT 15.00;

-- Daily revenue snapshots for trend chart
CREATE TABLE IF NOT EXISTS daily_revenue (
  date DATE NOT NULL PRIMARY KEY,
  orders INT NOT NULL DEFAULT 0,
  revenue_cents INT NOT NULL DEFAULT 0,
  new_customers INT NOT NULL DEFAULT 0,
  repeat_customers INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Language/market performance aggregates (materialized view pattern)
CREATE TABLE IF NOT EXISTS market_metrics (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  lang TEXT NOT NULL,
  period_start DATE NOT NULL,
  period_end DATE NOT NULL,
  scans INT NOT NULL DEFAULT 0,
  activations INT NOT NULL DEFAULT 0,
  completions INT NOT NULL DEFAULT 0,
  orders INT NOT NULL DEFAULT 0,
  revenue_cents INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (lang, period_start, period_end)
);

-- ─── Indexes ────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders (customer_email);
CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders (customer_id);
CREATE INDEX IF NOT EXISTS idx_daily_revenue_date ON daily_revenue (date);
CREATE INDEX IF NOT EXISTS idx_market_metrics_lang ON market_metrics (lang, period_start);

-- ─── RLS ────────────────────────────────────────────────────────────────────

ALTER TABLE daily_revenue ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_metrics ENABLE ROW LEVEL SECURITY;

CREATE POLICY "daily_revenue_read" ON daily_revenue FOR SELECT USING (TRUE);
CREATE POLICY "market_metrics_read" ON market_metrics FOR SELECT USING (TRUE);

-- ─── Helper function: refresh daily revenue from orders ─────────────────────

CREATE OR REPLACE FUNCTION refresh_daily_revenue()
RETURNS VOID AS $$
BEGIN
  INSERT INTO daily_revenue (date, orders, revenue_cents, new_customers, repeat_customers)
  SELECT
    DATE(o.created_at) AS date,
    COUNT(*) AS orders,
    COALESCE(SUM(o.revenue_cents), 0) AS revenue_cents,
    COUNT(*) FILTER (WHERE NOT o.is_repeat_customer) AS new_customers,
    COUNT(*) FILTER (WHERE o.is_repeat_customer) AS repeat_customers
  FROM orders o
  GROUP BY DATE(o.created_at)
  ON CONFLICT (date)
  DO UPDATE SET
    orders = EXCLUDED.orders,
    revenue_cents = EXCLUDED.revenue_cents,
    new_customers = EXCLUDED.new_customers,
    repeat_customers = EXCLUDED.repeat_customers,
    created_at = NOW();
END;
$$ LANGUAGE plpgsql;
