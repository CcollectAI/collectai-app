-- ============================================================================
-- Bug Fix Audit Migration (2026-02-19)
-- ============================================================================
-- 1. Add corrected_by column to training_items for correction audit trail
-- 2. Add processed_webhook_events table for multi-worker Stripe dedup
-- 3. Add price_history table (supports trend endpoint from iteration round)
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. training_items: corrected_by audit trail
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'training_items'
          AND column_name = 'corrected_by'
    ) THEN
        ALTER TABLE public.training_items
            ADD COLUMN corrected_by UUID REFERENCES auth.users(id) ON DELETE SET NULL;
        COMMENT ON COLUMN public.training_items.corrected_by
            IS 'User who last submitted a correction for this training item';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_training_items_corrected_by
    ON public.training_items (corrected_by)
    WHERE corrected_by IS NOT NULL;


-- ---------------------------------------------------------------------------
-- 2. processed_webhook_events: DB-based Stripe webhook idempotency
-- ---------------------------------------------------------------------------
-- Replaces in-memory LRU dedup for multi-worker deployments.
-- The billing_router checks this table before processing any webhook event.

CREATE TABLE IF NOT EXISTS processed_webhook_events (
    event_id    TEXT PRIMARY KEY,
    event_type  TEXT NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE processed_webhook_events
    IS 'Stripe webhook idempotency — prevents duplicate event processing across workers';

-- Auto-cleanup: remove events older than 7 days to prevent unbounded growth.
-- Run via pg_cron or a periodic worker:
--   DELETE FROM processed_webhook_events WHERE processed_at < now() - interval '7 days';

CREATE INDEX IF NOT EXISTS idx_processed_webhook_events_processed_at
    ON processed_webhook_events (processed_at);

-- RLS: deny all direct access (only backend service role writes)
ALTER TABLE processed_webhook_events ENABLE ROW LEVEL SECURITY;

-- No policies = deny all for authenticated/anon roles


-- ---------------------------------------------------------------------------
-- 3. price_history table (supports GET /predict/trend/{item_id})
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS price_history (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id     UUID NOT NULL,
    price_eur   NUMERIC(12, 2) NOT NULL,
    source      TEXT,           -- 'prediction', 'market_hit', 'user_feedback'
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_price_history_item_recorded
    ON price_history (item_id, recorded_at DESC);

ALTER TABLE price_history ENABLE ROW LEVEL SECURITY;

-- Users can read price history for their own items
CREATE POLICY price_history_read ON price_history
    FOR SELECT USING (
        item_id IN (SELECT id FROM portfolio_items WHERE user_id = auth.uid())
    );
