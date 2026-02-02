-- User Price Alerts table for alerts_feature_router.py
-- Supports: below_threshold, category_trend, high_prediction alert types

BEGIN;

CREATE TABLE IF NOT EXISTS public.user_price_alerts (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL,
  item_id         uuid,                                      -- specific item to watch; null for category/global
  category        text,                                      -- e.g. 'mtg', 'funko', 'pokemon'
  trigger_type    text NOT NULL CHECK (trigger_type IN ('below_threshold', 'category_trend', 'high_prediction')),
  threshold_value numeric(12,2),                             -- for below_threshold triggers
  direction       text CHECK (direction IS NULL OR direction IN ('up', 'down')),  -- for trend triggers
  active          boolean NOT NULL DEFAULT true,
  created_at      timestamptz NOT NULL DEFAULT now(),
  last_triggered_at timestamptz,
  metadata        jsonb NOT NULL DEFAULT '{}'::jsonb
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_user_price_alerts_user_id ON public.user_price_alerts(user_id);
CREATE INDEX IF NOT EXISTS idx_user_price_alerts_user_active ON public.user_price_alerts(user_id, active) WHERE active = true;
CREATE INDEX IF NOT EXISTS idx_user_price_alerts_item_id ON public.user_price_alerts(item_id) WHERE item_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_user_price_alerts_category ON public.user_price_alerts(category) WHERE category IS NOT NULL;

-- Enable RLS
ALTER TABLE public.user_price_alerts ENABLE ROW LEVEL SECURITY;

-- RLS policies: users can only see/modify their own alerts
CREATE POLICY "user_price_alerts_select_own" ON public.user_price_alerts
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "user_price_alerts_insert_own" ON public.user_price_alerts
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "user_price_alerts_update_own" ON public.user_price_alerts
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "user_price_alerts_delete_own" ON public.user_price_alerts
  FOR DELETE USING (auth.uid() = user_id);

COMMIT;
