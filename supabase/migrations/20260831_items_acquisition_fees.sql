-- Acquisition fees: the missing half of a true cost basis.
--
-- WHY: portfolio_router computes cost_basis from purchase_price_eur alone, so
-- unrealized_pl is measured against the STICKER price and overstates every gain
-- for anyone who paid tax, postage or grading. docs/COLLECTOR_DEMAND.md §5:
-- a EUR 900 card + EUR 56.25 tax is a EUR 956.25 basis, and selling at EUR 1000
-- looks like profit while being a loss once fees land.
--
-- PAIRED, deliberately, mirroring purchase_price / purchase_price_eur. The raw
-- half is what the member typed, in `purchase_currency`; the EUR half is what
-- every analytics reader sums. docs/ARCHITECTURE.md records that writing one
-- half of such a pair NEVER throws -- the reader defaults and the feature just
-- renders empty -- which is why both halves are written together by the single
-- route and NOT left to the trigger to infer.
--
-- ⚠️ NOT added to trg_items_sync_paired_columns on purpose. That trigger's guard
-- is `COALESCE(UPPER(BTRIM(purchase_currency)),'EUR') = 'EUR'`, i.e. a NULL
-- currency is treated AS EUR, which is exactly how a JPY amount ends up copied
-- into a euro column (~170x). PATCH /items/{item_id}/purchase converts with
-- app/lib/fx_service.py::convert_to_eur and writes both halves explicitly, so
-- there is nothing left for a trigger to guess.

ALTER TABLE public.items
  ADD COLUMN IF NOT EXISTS acquisition_fees     numeric,
  ADD COLUMN IF NOT EXISTS acquisition_fees_eur numeric;

COMMENT ON COLUMN public.items.acquisition_fees IS
  'Tax, inbound shipping, grading submission etc. paid to ACQUIRE this item, in purchase_currency. Raw half of a pair; see acquisition_fees_eur.';
COMMENT ON COLUMN public.items.acquisition_fees_eur IS
  'acquisition_fees converted to EUR. The half every analytics reader sums -- current_value is q50 in EUR, so mixing the raw half onto that axis would mix currencies.';

-- Post-write assertion, per the root-cause essay rule: prove the columns exist
-- and are nullable numerics rather than trusting ADD COLUMN IF NOT EXISTS,
-- which is name-idempotent and NOT shape-idempotent
-- (learning_create_if_not_exists_silently_noops).
DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n
    FROM information_schema.columns
   WHERE table_schema = 'public' AND table_name = 'items'
     AND column_name IN ('acquisition_fees', 'acquisition_fees_eur')
     AND data_type = 'numeric' AND is_nullable = 'YES';
  IF n <> 2 THEN
    RAISE EXCEPTION 'acquisition fee columns missing or wrong shape: found % of 2 nullable numerics', n;
  END IF;
END $$;
