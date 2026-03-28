-- ============================================================================
-- KPI Dashboard tables for SammySam TikTok Pod Campaign
-- Run this migration in your Supabase SQL editor to set up tracking tables.
-- ============================================================================

-- Creators: the micro-influencers in your pods
CREATE TABLE IF NOT EXISTS creators (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  name TEXT NOT NULL,
  handle TEXT NOT NULL,
  platform TEXT NOT NULL DEFAULT 'tiktok',
  language TEXT NOT NULL DEFAULT 'en',
  affiliate_code TEXT UNIQUE NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- KPI events: all funnel events, attributed to creator codes
CREATE TABLE IF NOT EXISTS kpi_events (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  event_name TEXT NOT NULL,
  kit_slug TEXT,
  step_id TEXT,
  affiliate_code TEXT,
  device_id TEXT,
  utm_source TEXT,
  utm_medium TEXT,
  utm_campaign TEXT,
  lang TEXT,
  properties JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Orders: synced from Shopify webhooks or manual entry
CREATE TABLE IF NOT EXISTS orders (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  shopify_order_id TEXT UNIQUE,
  affiliate_code TEXT,
  kit_slug TEXT,
  quantity INT NOT NULL DEFAULT 1,
  revenue_cents INT NOT NULL DEFAULT 0,
  currency TEXT NOT NULL DEFAULT 'EUR',
  customer_email TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Indexes ────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_kpi_events_name ON kpi_events (event_name);
CREATE INDEX IF NOT EXISTS idx_kpi_events_code ON kpi_events (affiliate_code);
CREATE INDEX IF NOT EXISTS idx_kpi_events_created ON kpi_events (created_at);
CREATE INDEX IF NOT EXISTS idx_kpi_events_device ON kpi_events (device_id);
CREATE INDEX IF NOT EXISTS idx_orders_code ON orders (affiliate_code);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders (created_at);

-- ─── RLS Policies ───────────────────────────────────────────────────────────

ALTER TABLE creators ENABLE ROW LEVEL SECURITY;
ALTER TABLE kpi_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

-- Anon can read creators (for admin dashboard)
CREATE POLICY "creators_read" ON creators FOR SELECT USING (TRUE);

-- Anon can read events (for admin dashboard)
CREATE POLICY "kpi_events_read" ON kpi_events FOR SELECT USING (TRUE);

-- Anon can insert events (client-side tracking from PWA)
CREATE POLICY "kpi_events_insert" ON kpi_events FOR INSERT WITH CHECK (TRUE);

-- Anon can read orders (for admin dashboard)
CREATE POLICY "orders_read" ON orders FOR SELECT USING (TRUE);

-- Orders insert: service role only (via webhook). No anon insert policy.
