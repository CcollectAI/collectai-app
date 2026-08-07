-- P2P tracking capture — display-only shipment visibility on an offer.
--
-- Facilitation without becoming a party: we store what the seller tells us and
-- render a link to the CARRIER's own page. See docs/P2P_MARKETPLACE_SPEC.md
-- §5b ("Sparrow may know everything and do nothing").
--
-- THE RULE THIS SCHEMA EXISTS TO HOLD: tracking is display-only. Nothing may
-- derive completion from it. `seller_confirmed_at` / `buyer_confirmed_at` stay
-- the ONLY completion signal, written only by confirm_exchange(). Polling a
-- carrier and flipping buyer_confirmed_at on "delivered" would substitute our
-- judgment for the buyer's — and we would own it when the box arrives empty.
-- That is the same class as labelling a listing "authenticated by Sparrow".
--
-- Additive only. No backfill: existing offers simply have no tracking.
BEGIN;

ALTER TABLE public.p2p_offers
    ADD COLUMN IF NOT EXISTS tracking_carrier text,
    ADD COLUMN IF NOT EXISTS tracking_code    text,
    ADD COLUMN IF NOT EXISTS tracking_set_at  timestamptz;

-- Length caps ONLY — deliberately no CHECK on the carrier VALUE.
--
-- The carrier list lives in `_CARRIER_TRACKING` in p2p_offers_router.py and
-- will grow. A value CHECK here would make adding a carrier a DDL change, and
-- DDL stales schema.lock.json, which hard-downs the API on the next bake
-- restart. It is also the exact shape of
-- learning_db_constraints_narrower_than_code ('fixed' vs 'fixed_price', and the
-- missing 'withdrawn' status) — both came from a CHECK narrower than the code
-- that wrote to it. Kept on one line so the learning name stays greppable.
--
-- These numbers MUST match TrackingIn.tracking_carrier / .tracking_code in
-- server/app/features/p2p_offers_router.py. Same type space (character length
-- of a text value), so the guard and the constraint cannot disagree at a
-- boundary — cf. learning_guard_must_match_constraint_type_space.
ALTER TABLE public.p2p_offers
    DROP CONSTRAINT IF EXISTS p2p_offers_tracking_len_check;
ALTER TABLE public.p2p_offers
    ADD CONSTRAINT p2p_offers_tracking_len_check CHECK (
        (tracking_carrier IS NULL OR length(tracking_carrier) <= 40)
        AND (tracking_code IS NULL OR length(tracking_code) <= 64)
    );

COMMENT ON COLUMN public.p2p_offers.tracking_carrier IS
    'Carrier key the seller selected. Resolved to a tracking URL by '
    '_CARRIER_TRACKING in p2p_offers_router.py; unknown keys render the code '
    'with no link rather than a link that 404s.';
COMMENT ON COLUMN public.p2p_offers.tracking_code IS
    'Seller-supplied consignment number. DISPLAY ONLY — must never be used to '
    'derive completion. See the header of this migration.';
COMMENT ON COLUMN public.p2p_offers.tracking_set_at IS
    'When the seller attached tracking. Not a shipment timestamp — we do not '
    'know when the carrier actually took it.';

COMMIT;
