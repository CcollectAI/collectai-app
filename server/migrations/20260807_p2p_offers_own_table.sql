-- P2P offers get their OWN table.
--
-- `public.offers` is NOT available: its FK points at `public.listings` (the
-- deal/mandate listings table), and app/agents/deal_completion.py and
-- deal_risk.py both JOIN offers -> listings. Repointing that FK would break
-- those agents; dropping it would leave listing_id ambiguously referencing
-- one of two tables with no way to tell which. Discovered by the Stage 2 E2E
-- raising offers_listing_id_fkey — a mocked test would have missed it.
BEGIN;

CREATE TABLE IF NOT EXISTS public.p2p_offers (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id   uuid NOT NULL REFERENCES public.marketplace_listings(id) ON DELETE CASCADE,
    buyer_id     uuid NOT NULL,
    seller_id    uuid NOT NULL,
    amount       numeric NOT NULL CHECK (amount > 0),
    currency     text NOT NULL DEFAULT 'EUR',
    status       text NOT NULL DEFAULT 'pending',
    message      text,
    counter_count integer NOT NULL DEFAULT 0,
    -- Two-sided completion. Grading is anchored to BOTH being set.
    seller_confirmed_at timestamptz,
    buyer_confirmed_at  timestamptz,
    -- Walking away after an accept is recorded, not punished — the only
    -- sanction available without a payment rail.
    withdrawn_by uuid,
    withdrawn_at timestamptz,
    expires_at   timestamptz,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT p2p_offers_status_check CHECK (status IN
        ('pending','countered','accepted','declined','cancelled','expired','shipped','completed')),
    CONSTRAINT p2p_offers_not_self CHECK (buyer_id <> seller_id)
);

CREATE INDEX IF NOT EXISTS idx_p2p_offers_listing ON public.p2p_offers (listing_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_p2p_offers_buyer   ON public.p2p_offers (buyer_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_p2p_offers_seller  ON public.p2p_offers (seller_id, status, created_at DESC);
-- One live offer per buyer per listing.
CREATE UNIQUE INDEX IF NOT EXISTS idx_p2p_offers_one_open
    ON public.p2p_offers (listing_id, buyer_id)
    WHERE status IN ('pending','countered','accepted');

ALTER TABLE public.p2p_offers ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS p2p_offers_party ON public.p2p_offers;
CREATE POLICY p2p_offers_party ON public.p2p_offers
    FOR SELECT USING (buyer_id = auth.uid() OR seller_id = auth.uid());

-- Repoint grades at the new table.
ALTER TABLE public.member_grades DROP CONSTRAINT IF EXISTS member_grades_offer_id_fkey;
ALTER TABLE public.member_grades
    ADD CONSTRAINT member_grades_offer_id_fkey
    FOREIGN KEY (offer_id) REFERENCES public.p2p_offers(id) ON DELETE CASCADE;

COMMIT;
