-- Smart Deal Agent: mandate-driven deal discovery + affiliate monetization
-- Tables: purchase_mandates, mandate_deals
-- Indexes for scan scheduling, user lookups, deal feeds
-- RLS: users only see their own mandates/deals

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- purchase_mandates — user-defined buying criteria
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.purchase_mandates (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id              uuid NOT NULL,
  name                 text NOT NULL,
  status               text NOT NULL DEFAULT 'active'
                       CHECK (status IN ('active','paused','exhausted','expired')),

  -- Search criteria (fed to MarketplaceAgent)
  search_query         text NOT NULL,
  category             text,
  condition_filter     text[] DEFAULT '{}',
  min_trust_score      numeric(3,2) DEFAULT 0.60,

  -- Spending controls
  max_price            numeric(12,2) NOT NULL,
  max_total_budget     numeric(12,2),
  spent_total          numeric(12,2) DEFAULT 0.00,
  cooldown_hours       int DEFAULT 24,

  -- Marketplace preferences
  allowed_sources      text[] DEFAULT '{}',
  region               text,

  -- Lifecycle
  expires_at           timestamptz,
  last_scan_at         timestamptz,
  last_deal_at         timestamptz,
  deals_found          int DEFAULT 0,
  deals_purchased      int DEFAULT 0,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.purchase_mandates IS 'User-defined buying mandates for the Smart Deal Agent';
COMMENT ON COLUMN public.purchase_mandates.search_query IS 'Query string fed to MarketplaceAgent.aggregate_search()';
COMMENT ON COLUMN public.purchase_mandates.min_trust_score IS 'Minimum provenance score (0.00-1.00) for a deal to pass policy';
COMMENT ON COLUMN public.purchase_mandates.cooldown_hours IS 'Min hours between deal notifications for this mandate';

-- ─────────────────────────────────────────────────────────────────────────────
-- mandate_deals — discovered deals matched to mandates
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.mandate_deals (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  mandate_id        uuid NOT NULL REFERENCES public.purchase_mandates(id) ON DELETE CASCADE,
  user_id           uuid NOT NULL,
  status            text NOT NULL DEFAULT 'discovered'
                    CHECK (status IN (
                      'discovered',
                      'notified',
                      'clicked',
                      'purchased',
                      'declined',
                      'expired'
                    )),

  -- Listing snapshot
  listing_source    text NOT NULL,
  listing_url       text NOT NULL,
  affiliate_url     text,
  listing_title     text NOT NULL,
  listing_price     numeric(12,2) NOT NULL,
  listing_currency  text NOT NULL DEFAULT 'EUR',
  listing_condition text,
  listing_image_url text,
  listing_seller    text,
  listing_ended     boolean DEFAULT false,

  -- Agent scoring
  provenance_score  numeric(4,3),
  deal_score        numeric(4,3),
  price_vs_q50_pct  numeric(5,1),
  predicted_q50     numeric(12,2),
  predicted_q10     numeric(12,2),
  predicted_q90     numeric(12,2),

  -- Policy verdict
  policy_passed     boolean NOT NULL DEFAULT true,
  policy_reasons    jsonb DEFAULT '[]',

  -- Affiliate tracking
  affiliate_source  text,
  affiliate_click   boolean DEFAULT false,
  estimated_commission numeric(12,2),

  -- Confirmation
  confirmed_price   numeric(12,2),
  added_item_id     uuid,

  -- Timestamps
  discovered_at     timestamptz NOT NULL DEFAULT now(),
  notified_at       timestamptz,
  clicked_at        timestamptz,
  purchased_at      timestamptz,
  created_at        timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.mandate_deals IS 'Deals discovered by the Smart Deal Agent, linked to purchase mandates';
COMMENT ON COLUMN public.mandate_deals.deal_score IS 'Composite score (0-1) combining provenance, price, and recency';
COMMENT ON COLUMN public.mandate_deals.price_vs_q50_pct IS 'Percentage diff vs predicted median, e.g. -15.2 = 15% below q50';

-- ─────────────────────────────────────────────────────────────────────────────
-- Indexes
-- ─────────────────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_mandates_user_active
  ON public.purchase_mandates(user_id, status) WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_mandates_scan
  ON public.purchase_mandates(last_scan_at ASC NULLS FIRST) WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_deals_mandate
  ON public.mandate_deals(mandate_id, status);

CREATE INDEX IF NOT EXISTS idx_deals_user_recent
  ON public.mandate_deals(user_id, discovered_at DESC);

CREATE INDEX IF NOT EXISTS idx_deals_user_status
  ON public.mandate_deals(user_id, status);

-- Dedup lookups: URL per mandate for active deals
CREATE INDEX IF NOT EXISTS idx_deals_mandate_url
  ON public.mandate_deals(mandate_id, listing_url)
  WHERE status NOT IN ('expired', 'declined');

-- List mandates sort order
CREATE INDEX IF NOT EXISTS idx_mandates_user_created
  ON public.purchase_mandates(user_id, created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- Row Level Security
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.purchase_mandates ENABLE ROW LEVEL SECURITY;

CREATE POLICY mandates_user_own ON public.purchase_mandates
  FOR ALL TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

ALTER TABLE public.mandate_deals ENABLE ROW LEVEL SECURITY;

CREATE POLICY deals_user_own ON public.mandate_deals
  FOR ALL TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

COMMIT;
