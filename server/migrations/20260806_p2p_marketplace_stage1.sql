-- P2P Marketplace, Stage 1 — user-to-user listings (NO payments)
--
-- See docs/P2P_MARKETPLACE_SPEC.md. Stage 1 is listings only: a seller lists
-- an item they own, a buyer taps through to chat. Sparrow never touches funds,
-- which is what keeps PSD2, chargebacks and most of DAC7 out of scope.
--
-- Design decision: REUSE `marketplace_listings` rather than a new table. It
-- already has 38 columns covering price/condition/shipping/status/fees and a
-- working router. A native listing is just one whose marketplace is 'sparrow'
-- and whose external_listing_id / listing_url stay NULL.
--
-- Everything here is ADDITIVE (new row, new nullable columns, new indexes).
-- No column is dropped or retyped, so existing readers cannot break.
-- NOTE: this is still DDL — regenerate schema.lock.json afterwards or the next
-- bake restart hard-downs the API (learning_schema_lock_staleness_on_restart).

BEGIN;

-- 1. Register Sparrow as a marketplace ------------------------------------
-- ON CONFLICT so re-running is safe. `key` is what code should match on; the
-- numeric id is assigned by the sequence and must never be hardcoded.
INSERT INTO public.marketplaces (key, name, enabled)
VALUES ('sparrow', 'Sparrow Collect (member listings)', true)
ON CONFLICT (key) DO UPDATE
    SET name = EXCLUDED.name,
        enabled = EXCLUDED.enabled;

-- 2. Native-listing columns -----------------------------------------------
-- All nullable: external listings leave them NULL and are unaffected.
ALTER TABLE public.marketplace_listings
    -- Denormalised so the snipe/supply writer does not need an items join.
    ADD COLUMN IF NOT EXISTS canonical_key text,
    ADD COLUMN IF NOT EXISTS category text,
    -- Free-text location; Stage 1 has no structured shipping.
    ADD COLUMN IF NOT EXISTS ships_from text,
    -- Set when the seller marks it sold/withdrawn, so the supply hook knows to
    -- stale the market_hits row. A snipe that opens a sold listing is worse
    -- than no snipe (docs/P2P_MARKETPLACE_SPEC.md §4).
    ADD COLUMN IF NOT EXISTS delisted_at timestamptz,
    -- DSA notice-and-action: a report count lets moderation triage without a
    -- separate join on first load.
    ADD COLUMN IF NOT EXISTS reports_count integer NOT NULL DEFAULT 0;

-- 3. Indexes ---------------------------------------------------------------
-- Browse: active native listings, newest first.
CREATE INDEX IF NOT EXISTS idx_mkt_listings_sparrow_active
    ON public.marketplace_listings (marketplace_id, status, created_at DESC)
    WHERE delisted_at IS NULL;

-- Catalog-item page: "other members selling this".
CREATE INDEX IF NOT EXISTS idx_mkt_listings_canonical
    ON public.marketplace_listings (canonical_key)
    WHERE canonical_key IS NOT NULL;

-- Seller's own listings.
CREATE INDEX IF NOT EXISTS idx_mkt_listings_user
    ON public.marketplace_listings (user_id, created_at DESC);

-- 4. Abuse reports ---------------------------------------------------------
-- DSA notice-and-action requires acting on notice and giving a statement of
-- reasons. The micro-enterprise exemption does NOT cover this obligation.
CREATE TABLE IF NOT EXISTS public.listing_reports (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id   uuid NOT NULL REFERENCES public.marketplace_listings(id) ON DELETE CASCADE,
    reporter_id  uuid NOT NULL,
    reason       text NOT NULL,
    detail       text,
    -- open -> actioned | dismissed. `resolution_note` is the statement of
    -- reasons owed to the reporter and the seller.
    status       text NOT NULL DEFAULT 'open',
    resolution_note text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    resolved_at  timestamptz,
    CONSTRAINT listing_reports_status_check
        CHECK (status IN ('open', 'actioned', 'dismissed')),
    -- One open report per user per listing; re-reporting after resolution is
    -- allowed, which is why resolved rows are excluded from the constraint.
    CONSTRAINT listing_reports_reason_len CHECK (char_length(reason) BETWEEN 3 AND 120)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_listing_reports_one_open
    ON public.listing_reports (listing_id, reporter_id)
    WHERE status = 'open';

CREATE INDEX IF NOT EXISTS idx_listing_reports_triage
    ON public.listing_reports (status, created_at DESC)
    WHERE status = 'open';

-- 5. RLS -------------------------------------------------------------------
ALTER TABLE public.listing_reports ENABLE ROW LEVEL SECURITY;

-- Reporters see their own reports; the service role sees everything.
DROP POLICY IF EXISTS listing_reports_own ON public.listing_reports;
CREATE POLICY listing_reports_own ON public.listing_reports
    FOR SELECT USING (reporter_id = auth.uid());

DROP POLICY IF EXISTS listing_reports_insert ON public.listing_reports;
CREATE POLICY listing_reports_insert ON public.listing_reports
    FOR INSERT WITH CHECK (reporter_id = auth.uid());

COMMIT;
