-- Round 4 silent-failure sweep (2026-04-20): re-apply price CHECK after
-- partitioning. The 20260418_invariant_checks.sql migration added a
-- `market_hits_price_sane` CHECK (price/price_eur <= €20M) which silently
-- disappeared when market_hits was partitioned on 2026-04-19 (R50m part 2).
-- Partitioning creates new child tables; constraints on the pre-partition
-- table don't carry over to the new parent's children.
--
-- Evidence of the gap: 289 rows with price_eur = €1,546,171,702 (Crawl4AI
-- parsing "Site Statistics" pages as product listings) landed during the
-- 24h after partitioning. Writer-side filter in persist_comps_to_db blocks
-- new ones (round 3); this CHECK ensures the DB layer can never drift again.
--
-- Approach: clean violators first (there's no way to VALIDATE a CHECK that
-- existing rows fail), then add constraint on the parent table with NO
-- INHERIT — Postgres propagates to all current + future partitions.

-- ---------------------------------------------------------------------------
-- 1. Delete the 290 known garbage rows. All share title='Site Statistics'
-- and the identical €1.55B price — they're not recoverable real listings.
-- ---------------------------------------------------------------------------
DELETE FROM public.market_hits
WHERE price_eur > 20000000
   OR price > 20000000;

-- ---------------------------------------------------------------------------
-- 2. Attach CHECK constraint to the partitioned parent. Postgres propagates
-- to every existing and future partition automatically.
-- ---------------------------------------------------------------------------
ALTER TABLE public.market_hits
    DROP CONSTRAINT IF EXISTS market_hits_price_sane;

ALTER TABLE public.market_hits
    ADD CONSTRAINT market_hits_price_sane
    CHECK (
        (price IS NULL OR price <= 20000000)
        AND (price_eur IS NULL OR price_eur <= 20000000)
    );
-- NOT VALID intentionally omitted — DELETE above cleared all violators, so
-- validation runs immediately and blocks any future regression.
