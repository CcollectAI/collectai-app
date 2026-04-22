-- 2026-04-22: Promote 4 lazy-CREATE / missing tables to proper migrations.
-- Routers had `CREATE TABLE IF NOT EXISTS …` inline in the request hot path
-- (or no CREATE at all for quickscan_history), which created cold-start race
-- conditions and meant cross-router queries 500'd until the right writer ran
-- first. Surfaced during the 2026-04-22 e2e schema audit.

-- 1. event_tickets — billing_router._handle_ticket_checkout_completed
CREATE TABLE IF NOT EXISTS public.event_tickets (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id            UUID NOT NULL,
  user_id             UUID NOT NULL,
  stripe_session_id   VARCHAR(255),
  amount_cents        INTEGER NOT NULL,
  fee_cents           INTEGER NOT NULL DEFAULT 0,
  status              VARCHAR(50) NOT NULL DEFAULT 'paid',
  created_at          TIMESTAMPTZ DEFAULT now(),
  UNIQUE (event_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_event_tickets_user
  ON public.event_tickets (user_id, created_at DESC);

-- 2. sponsor_subscriptions — billing_router._handle_sponsor_subscription_completed
CREATE TABLE IF NOT EXISTS public.sponsor_subscriptions (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id               UUID NOT NULL,
  user_id                  UUID NOT NULL,
  stripe_customer_id       VARCHAR(255),
  stripe_subscription_id   VARCHAR(255),
  tier                     VARCHAR(50) NOT NULL DEFAULT 'featured',
  status                   VARCHAR(50) NOT NULL DEFAULT 'active',
  current_period_end       TIMESTAMPTZ,
  created_at               TIMESTAMPTZ DEFAULT now(),
  updated_at               TIMESTAMPTZ DEFAULT now(),
  UNIQUE (company_id)
);
CREATE INDEX IF NOT EXISTS idx_sponsor_subscriptions_user
  ON public.sponsor_subscriptions (user_id);
CREATE INDEX IF NOT EXISTS idx_sponsor_subscriptions_stripe
  ON public.sponsor_subscriptions (stripe_subscription_id);

-- 3. notification_history — push.py + notification_router + value_summary_router.
--    Canonical column is `type` (push.py writer + 002_add_critical_missing_indexes
--    confirm). value_summary_router was filtering on `category` which never
--    existed — patched in this same change.
CREATE TABLE IF NOT EXISTS public.notification_history (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL,
  type        TEXT NOT NULL,
  title       TEXT NOT NULL,
  body        TEXT,
  data        JSONB DEFAULT '{}'::jsonb,
  deep_link   TEXT,
  read_at     TIMESTAMPTZ,
  created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_notification_history_user_created
  ON public.notification_history (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notification_history_user_unread
  ON public.notification_history (user_id) WHERE read_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_notification_history_user_type
  ON public.notification_history (user_id, type, created_at DESC);

-- 4. quickscan_history — value_summary_router scan-count.
--    Currently no writer; table is created so the COUNT query returns 0
--    instead of 500. When QuickScan flow gains analytics persistence, it
--    writes here. Schema kept intentionally minimal until the writer lands.
CREATE TABLE IF NOT EXISTS public.quickscan_history (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL,
  scanned_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  result_kind  TEXT,         -- e.g. 'identified', 'unknown', 'low_confidence'
  payload      JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_quickscan_history_user_time
  ON public.quickscan_history (user_id, scanned_at DESC);
