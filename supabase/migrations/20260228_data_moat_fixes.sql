-- Data moat fixes: CHECK constraint expansion, missing columns, broken view
-- Migration: 20260228_data_moat_fixes.sql

BEGIN;

-- ============================================================================
-- 1. Expand demand_signals CHECK constraint to include new signal types
--    Original only allowed 5 types; code now emits 10.
-- ============================================================================

ALTER TABLE public.demand_signals
    DROP CONSTRAINT IF EXISTS demand_signals_signal_type_check;

ALTER TABLE public.demand_signals
    ADD CONSTRAINT demand_signals_signal_type_check
    CHECK (signal_type IN (
        'mandate_created', 'search_query', 'item_viewed',
        'price_alert_set', 'watchlist_add',
        'item_scanned', 'item_added', 'catalog_browsed',
        'category_viewed', 'collection_viewed'
    ));

-- ============================================================================
-- 2. Add item_ref and generated_at columns to price_predictions
--    The valuation_worker writes to these columns but they were never migrated.
--    item_ref is a text key (e.g. "pokemon:charizard_base_set") used for
--    non-UUID item matching. generated_at tracks when the prediction was made.
-- ============================================================================

ALTER TABLE public.price_predictions
    ADD COLUMN IF NOT EXISTS item_ref text,
    ADD COLUMN IF NOT EXISTS generated_at timestamptz DEFAULT now();

-- Backfill generated_at from asof for existing rows
UPDATE public.price_predictions SET generated_at = asof WHERE generated_at IS NULL AND asof IS NOT NULL;

-- Index for valuation_worker lookups by item_ref
CREATE INDEX IF NOT EXISTS idx_price_predictions_item_ref
    ON public.price_predictions(item_ref)
    WHERE item_ref IS NOT NULL;

-- ============================================================================
-- 3. Add missing columns to market_hits used by valuation_worker
--    item_ref: text key for grouping hits (same item across sources)
--    observed_at: when listing was observed (falls back to created_at)
--    processed: flag for valuation_worker to track which hits it has processed
-- ============================================================================

ALTER TABLE public.market_hits
    ADD COLUMN IF NOT EXISTS item_ref text,
    ADD COLUMN IF NOT EXISTS observed_at timestamptz DEFAULT now(),
    ADD COLUMN IF NOT EXISTS processed boolean DEFAULT false;

-- Backfill: item_ref from normalized_key, observed_at from created_at
UPDATE public.market_hits SET item_ref = normalized_key WHERE item_ref IS NULL AND normalized_key IS NOT NULL;
UPDATE public.market_hits SET observed_at = created_at WHERE observed_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_market_hits_item_ref
    ON public.market_hits(item_ref)
    WHERE item_ref IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_market_hits_unprocessed
    ON public.market_hits(processed)
    WHERE processed = false;

-- ============================================================================
-- 4. Fix v_item_with_evidence view: pp2.nk does not exist, use item_id
-- ============================================================================

CREATE OR REPLACE VIEW public.v_item_with_evidence AS
SELECT
    i.id,
    i.user_id,
    i.name,
    i.category,
    i.subtype_id,
    i.taxonomy_version,
    i.collections,
    i.attributes_json,
    pp.q10,
    pp.q50,
    pp.q90,
    pp.conf_score AS confidence,
    pp.explanation,
    pp.evidence_summary,
    pp.evidence_hit_ids,
    pp.model_version,
    pp.created_at AS prediction_at
FROM public.items i
LEFT JOIN LATERAL (
    SELECT *
    FROM public.price_predictions pp2
    WHERE pp2.item_id = i.id
    ORDER BY pp2.created_at DESC
    LIMIT 1
) pp ON true;

COMMIT;
