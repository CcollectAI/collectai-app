-- DAC7 reportable-seller tracking.
--
-- WHY THIS EXISTS
-- -----------------------------------------------------------------------------
-- `app/legal/marketplace-terms.tsx` §6 promises members:
--
--     "Most members are below the reporting threshold — fewer than 30 sales and
--      under EUR 2,000 in a year — and are not reported. If you are above it, we
--      will ask you for the information we need and will tell you before
--      anything about you is reported."
--
-- Nothing implemented that. The threshold was a sentence in a legal screen with
-- no counter behind it, so we could neither tell a member they had crossed it
-- nor demonstrate that everyone else had not. Spec §5a is explicit that the
-- obligation is live NOW (DAC7 turns on the consideration being KNOWN, and
-- `p2p_offers.amount` is known and confirmed by both parties) — and that the
-- cost is "registration plus enough data to DEMONSTRATE exclusion".
--
-- This table is that data.
--
-- THE RULE, AND WHY IT IS `OR`
-- -----------------------------------------------------------------------------
-- A seller is an EXCLUDED SELLER only when BOTH hold in a calendar year:
--     fewer than 30 relevant activities  AND  consideration at or under EUR 2,000
--
-- So a seller becomes REPORTABLE when EITHER is breached:
--     sales_count >= 30   OR   gross_eur > 2000
--
-- Getting that connective wrong in either direction is the whole risk: `AND`
-- would under-report (a member with 40 sales of EUR 20 would be missed), and
-- reporting on `<30 AND <2000` inverted would report almost everyone.
--
-- WHAT COUNTS
-- -----------------------------------------------------------------------------
-- Only COMPLETED trades, and only the SELLER side. A pending or accepted offer
-- is not consideration — nothing has happened yet — and the buyer is not the
-- reportable party. The amount is `p2p_offers.amount`, the AGREED figure after
-- any counter, which is the same figure `_sold_comp_hook` treats as the sale
-- price (§1g). Using the listing's asking price would overstate every seller.
--
-- Per CALENDAR year, because that is the reporting period.

BEGIN;

CREATE TABLE IF NOT EXISTS public.dac7_seller_year (
    user_id           uuid        NOT NULL,
    year              integer     NOT NULL,
    sales_count       integer     NOT NULL DEFAULT 0,
    gross_eur         numeric     NOT NULL DEFAULT 0,
    -- Set the moment the seller crosses either limb. Never cleared: crossing is
    -- a fact about the year, and a refund-driven dip below the line does not
    -- un-report a year already reported.
    reportable_at     timestamptz,
    -- When we TOLD them. The terms promise notice BEFORE anything is reported,
    -- so this is the evidence that the promise was kept — and the guard that
    -- stops us telling them again on every subsequent sale.
    notified_at       timestamptz,
    -- Filled once the member supplies what DAC7 requires (name, address, TIN,
    -- date of birth). Null while outstanding — this is what "we will ask you
    -- for the information we need" resolves to.
    details_provided_at timestamptz,
    updated_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, year)
);

COMMENT ON TABLE public.dac7_seller_year IS
    'Per-seller, per-calendar-year DAC7 counters. Reportable when sales_count >= 30 OR gross_eur > 2000 (the excluded-seller test is fewer than 30 AND at most 2000, so either breach makes a seller reportable). Written by _dac7_accrue on trade completion.';

-- Finding reportable sellers for a year is the ONLY query this table exists to
-- answer quickly.
CREATE INDEX IF NOT EXISTS idx_dac7_reportable
    ON public.dac7_seller_year (year)
    WHERE reportable_at IS NOT NULL;

-- Backend-only: the counters are derived, and a client that could write them
-- could write itself out of a reporting obligation.
ALTER TABLE public.dac7_seller_year ENABLE ROW LEVEL SECURITY;

COMMIT;
