-- RevenueCat: record mobile IAP subscriptions and build a revenue ledger.
--
-- Context: mobile Pro/Premium purchases go through RevenueCat/StoreKit, but the
-- only billing webhook was Stripe (billing_router.py). The subscriptions table
-- therefore had zero paid rows and mobile revenue was invisible server-side —
-- customerInfo on the client was the only source of truth. No creator payout
-- could be computed from anything queryable.
--
-- Two changes:
--   1. subscriptions gains provider + RevenueCat identity columns. It stays
--      current-state (UNIQUE user_id) — "what plan is this user on now".
--   2. subscription_events is a new append-only ledger. Payouts are computed by
--      summing this, because a subscription that renews 12 times is 12 revenue
--      events but only ever one subscriptions row.

-- ─── 1. subscriptions: provider + RevenueCat identity ───────────────────────

ALTER TABLE public.subscriptions
  ADD COLUMN IF NOT EXISTS provider TEXT NOT NULL DEFAULT 'stripe';

-- Existing rows predate RevenueCat and are all Stripe, which the default covers.
ALTER TABLE public.subscriptions
  DROP CONSTRAINT IF EXISTS subscriptions_provider_check;
ALTER TABLE public.subscriptions
  ADD CONSTRAINT subscriptions_provider_check
  CHECK (provider IN ('stripe', 'revenuecat'));

ALTER TABLE public.subscriptions
  ADD COLUMN IF NOT EXISTS revenuecat_app_user_id TEXT;
ALTER TABLE public.subscriptions
  ADD COLUMN IF NOT EXISTS revenuecat_product_id TEXT;

COMMENT ON COLUMN public.subscriptions.revenuecat_app_user_id IS
  'RevenueCat app_user_id. Equals auth.users.id — purchases.ts calls Purchases.logIn(userId).';

CREATE INDEX IF NOT EXISTS idx_subscriptions_rc_app_user
  ON public.subscriptions (revenuecat_app_user_id)
  WHERE revenuecat_app_user_id IS NOT NULL;

-- The Stripe handler writes 'active' on checkout; RevenueCat also emits
-- expirations and billing issues, so widen the allowed statuses.
ALTER TABLE public.subscriptions
  DROP CONSTRAINT IF EXISTS subscriptions_status_check;
ALTER TABLE public.subscriptions
  ADD CONSTRAINT subscriptions_status_check
  CHECK (status IN ('active', 'past_due', 'canceled', 'unpaid', 'trialing', 'expired', 'paused'));

-- ─── 2. subscription_events: the revenue ledger ─────────────────────────────

CREATE TABLE IF NOT EXISTS public.subscription_events (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  -- RevenueCat's event id. UNIQUE so a webhook retry cannot double-credit a
  -- creator: the whole payout depends on this not being double-counted.
  event_id          TEXT NOT NULL UNIQUE,
  event_type        TEXT NOT NULL,
  provider          TEXT NOT NULL DEFAULT 'revenuecat',
  user_id           UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  app_user_id       TEXT,
  product_id        TEXT,
  plan              TEXT,
  store             TEXT,
  environment       TEXT,
  -- Gross, in the purchase currency's minor units. Net-to-you is gross minus
  -- store commission; RevenueCat sends takehome_percentage for that.
  revenue_cents     INTEGER NOT NULL DEFAULT 0,
  currency          TEXT,
  takehome_percentage NUMERIC(5,4),
  -- Denormalised deliberately: attribution must be frozen at the moment of the
  -- transaction. Joining live to profiles.referred_by_code would silently
  -- rewrite historical payouts if a code were ever corrected.
  affiliate_code    TEXT,
  occurred_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  raw               JSONB
);

CREATE INDEX IF NOT EXISTS idx_subscription_events_affiliate
  ON public.subscription_events (affiliate_code, occurred_at DESC)
  WHERE affiliate_code IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_subscription_events_user
  ON public.subscription_events (user_id, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_subscription_events_occurred
  ON public.subscription_events (occurred_at DESC);

-- ─── RLS ────────────────────────────────────────────────────────────────────
-- Revenue is not user-facing. The webhook writes with the service role, which
-- bypasses RLS; enabling it with no policy denies every anon/authenticated read.

ALTER TABLE public.subscription_events ENABLE ROW LEVEL SECURITY;
