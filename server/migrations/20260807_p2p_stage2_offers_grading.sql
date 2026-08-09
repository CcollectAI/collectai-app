-- P2P Stage 2 — offers, two-sided completion, mutual grading, shipping reach
--
-- Decisions this encodes (confirmed 2026-08-07), and why each matters:
--
--  * ACCEPT = agreement to transact, NOT a lock. The listing is marked
--    reserved and chat opens, but either side can still walk. We have no
--    payment rail, so a hard reserve is unenforceable and would let a bad
--    actor serially block competitors' listings for free. Walking away is
--    RECORDED instead, and feeds credibility.
--  * COMPLETION IS TWO-SIDED. Seller marks sent, buyer marks received.
--    Grading unlocks only when both have. A single actor with two accounts
--    can still collude, but it costs two-sided intent — a lone account
--    cannot farm ratings, which is the failure mode that makes ratings
--    worthless at low volume.
--  * GRADES ARE THUMBS, not stars. Stars cluster at 5 and one 3-star looks
--    damning at low volume. Hidden below 3 grades for the same reason.
--
-- Additive only: new columns are nullable or defaulted, new tables are new.
-- STILL DDL — regenerate schema.lock.json after applying, or the next bake
-- restart hard-downs the API (learning_schema_lock_staleness_on_restart).

BEGIN;

-- 1. Shipping reach -------------------------------------------------------
-- Country + a ships-to list, not a rates engine. This is enough to stop the
-- main disappointment (finding the perfect item that will not ship to you)
-- without asking members to fill in carrier tables they will get wrong.
ALTER TABLE public.marketplace_listings
    ADD COLUMN IF NOT EXISTS ships_from_country text,
    -- ISO-3166-2 codes, or the sentinel 'WORLD'. An empty array means the
    -- seller has not said, which readers must treat as "unknown", NOT as
    -- "ships nowhere" — an empty-means-none reading would silently hide
    -- every legacy listing.
    ADD COLUMN IF NOT EXISTS ships_to text[] NOT NULL DEFAULT '{}',
    -- Set when an offer is accepted. Soft signal, not a lock: browse still
    -- shows the listing, the UI just marks it spoken for.
    ADD COLUMN IF NOT EXISTS reserved_offer_id uuid,
    ADD COLUMN IF NOT EXISTS reserved_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_mkt_listings_ships_from
    ON public.marketplace_listings (ships_from_country)
    WHERE ships_from_country IS NOT NULL;

-- 2. Two-sided completion on offers ---------------------------------------
-- The existing offers_status_chk already allows shipped/completed, so the
-- lifecycle was anticipated; these columns are what make it verifiable.
ALTER TABLE public.offers
    ADD COLUMN IF NOT EXISTS seller_confirmed_at timestamptz,
    ADD COLUMN IF NOT EXISTS buyer_confirmed_at timestamptz,
    -- Recorded when someone walks after accepting. Feeds credibility — the
    -- honest alternative to a reserve we cannot enforce.
    ADD COLUMN IF NOT EXISTS withdrawn_by uuid,
    ADD COLUMN IF NOT EXISTS withdrawn_at timestamptz,
    ADD COLUMN IF NOT EXISTS currency text NOT NULL DEFAULT 'EUR';

CREATE INDEX IF NOT EXISTS idx_offers_listing
    ON public.offers (listing_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_offers_buyer
    ON public.offers (buyer_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_offers_seller
    ON public.offers (seller_id, status, created_at DESC);

-- 3. Mutual grading -------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.member_grades (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- The completed offer this grade is anchored to. NOT NULL and unique per
    -- rater: a grade with no trade behind it is exactly the farmable rating
    -- this design exists to prevent.
    offer_id    uuid NOT NULL REFERENCES public.offers(id) ON DELETE CASCADE,
    rater_id    uuid NOT NULL,
    ratee_id    uuid NOT NULL,
    -- 'positive' | 'negative'. Thumbs, not stars.
    verdict     text NOT NULL,
    note        text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT member_grades_verdict_check
        CHECK (verdict IN ('positive', 'negative')),
    CONSTRAINT member_grades_note_len
        CHECK (note IS NULL OR char_length(note) <= 500),
    -- You cannot grade yourself.
    CONSTRAINT member_grades_not_self CHECK (rater_id <> ratee_id)
);

-- One grade per rater per trade. Re-grading is an edit, not a second vote.
CREATE UNIQUE INDEX IF NOT EXISTS idx_member_grades_once
    ON public.member_grades (offer_id, rater_id);

CREATE INDEX IF NOT EXISTS idx_member_grades_ratee
    ON public.member_grades (ratee_id, created_at DESC);

ALTER TABLE public.member_grades ENABLE ROW LEVEL SECURITY;

-- Grades are public (that is the point), but only the rater may write one,
-- and only for themselves.
DROP POLICY IF EXISTS member_grades_read ON public.member_grades;
CREATE POLICY member_grades_read ON public.member_grades
    FOR SELECT USING (true);

DROP POLICY IF EXISTS member_grades_write ON public.member_grades;
CREATE POLICY member_grades_write ON public.member_grades
    FOR INSERT WITH CHECK (rater_id = auth.uid());

COMMIT;
