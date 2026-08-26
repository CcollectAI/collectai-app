-- Backfill market_hits.price for the Lorcast price-guide rows.
--
-- WHY
-- ---
-- `scripts/load_lorcana_direct.py` wrote `price_eur` and left `price` NULL on
-- every one of the 5,420 rows it loaded on 2026-08-15 12:09:26-28.
-- `valuation_worker.run_once()` selects its queue with
--
--     WHERE processed = false AND ... AND price IS NOT NULL
--
-- (mirroring the partial index `idx_market_hits_valuation_queue`) while the
-- SELECT list it actually values on is `COALESCE(price_eur, price)`. So a row
-- carrying only `price_eur` is perfectly usable and permanently invisible.
--
-- Measured consequence: lorcana had 5,420 sold comps, 0 rows in
-- `price_predictions` — ever — and 2,671 catalogue items with a sold comp that
-- stayed unpriced. The daily watchdog reported that as
-- "pricing coverage collapsed for lorcana: 57.9% ... a keying or crosswalk
-- fault", which named the wrong mechanism: the crosswalk
-- (`catalog_price_refs`, 5,416 rows built 2026-08-15) is intact and covers the
-- tcgcsv key space; the lorcast half never reached valuation at all.
--
-- Enumerated mechanically before writing this, over the whole table rather
-- than the reported category:
--
--   processed=false AND NOT is_listing AND seen_at > now()-'90 days'
--   AND price IS NULL AND price_eur IS NOT NULL
--     -> 5,420 rows, ALL provider='lorcast', ALL category lorcana. Nothing else
--        in 2,796,800 sold rows has this shape.
--
-- WHY price := price_eur IS CORRECT HERE, AND NOT IN GENERAL
-- ---------------------------------------------------------
-- `price` is the price in its ORIGINAL currency, `price_eur` the EUR
-- normalisation (marketplace_agent.py:887 binds raw_price / raw_currency /
-- price_eur in that order). Over the last 30 days 1,958 rows have
-- price <> price_eur, and all 1,958 are currency='USD'. The Lorcast mapper
-- converts to EUR before constructing the MarketHit, so these rows are
-- currency='EUR' and the two values are the same number by construction.
-- The `currency = 'EUR'` predicate below is load-bearing: it is what makes
-- this a restatement rather than a currency error, and it is the bug
-- learning_a_currency_column_needs_the_currency_applied already cost us once.
--
-- DML only, no DDL: `scripts/schema.lock.json` is unaffected and no bake
-- restart is required.
--
-- The writer is fixed in the same change (scripts/load_lorcana_direct.py now
-- lists `price` in its INSERT column list), so this backfill is not something
-- the next run will re-create.

UPDATE public.market_hits
   SET price = price_eur
 WHERE provider = 'lorcast'
   AND price IS NULL
   AND price_eur IS NOT NULL
   AND currency = 'EUR';

-- Post-write assertion at the writer — docs/DATA_SCALING_PLAN.md §10
-- ("Writer bugs hide in INSERT column lists"): the identical defect on
-- `category` was found by an audit alarm and fixed with "add to the list +
-- backfill", and the lesson recorded was that the missing half is the
-- assertion. Fail the migration rather than report success over a no-op.
DO $$
DECLARE
    stragglers bigint;
BEGIN
    SELECT count(*) INTO stragglers
      FROM public.market_hits
     WHERE provider = 'lorcast'
       AND price IS NULL
       AND price_eur IS NOT NULL
       AND currency = 'EUR';

    IF stragglers > 0 THEN
        RAISE EXCEPTION
            'backfill incomplete: % lorcast rows still have price NULL with a price_eur',
            stragglers;
    END IF;
END $$;
