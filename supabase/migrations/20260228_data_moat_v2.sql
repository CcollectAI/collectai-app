-- Data moat v2: ground truth feedback loop + geo demand segmentation
-- Migration: 20260228_data_moat_v2.sql

BEGIN;

-- ============================================================================
-- 1. Price ground truths table (feedback loop)
--    Records actual transaction prices from completed Deal Desk offers.
--    Compared against price_predictions to compute prediction error.
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.price_ground_truths (
    id           bigserial    PRIMARY KEY,
    item_id      uuid         NOT NULL REFERENCES public.items(id) ON DELETE CASCADE,
    actual_price numeric      NOT NULL CHECK (actual_price > 0),
    currency     text         NOT NULL DEFAULT 'EUR',
    source       text         NOT NULL DEFAULT 'deal_desk',
    prediction_q50 numeric,
    error_pct    numeric,
    recorded_at  timestamptz  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ground_truths_item
    ON public.price_ground_truths(item_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_ground_truths_recorded
    ON public.price_ground_truths(recorded_at DESC);

ALTER TABLE public.price_ground_truths ENABLE ROW LEVEL SECURITY;
CREATE POLICY ground_truths_service_only ON public.price_ground_truths
    FOR ALL USING (false);

-- ============================================================================
-- 2. Geographic columns on demand_signals
--    Allows regional demand segmentation (trending in Japan vs Europe etc.)
-- ============================================================================

ALTER TABLE public.demand_signals
    ADD COLUMN IF NOT EXISTS region       text,
    ADD COLUMN IF NOT EXISTS country_code text;

-- Index for geographic queries
CREATE INDEX IF NOT EXISTS idx_demand_signals_geo
    ON public.demand_signals(region, country_code)
    WHERE region IS NOT NULL;

COMMIT;
