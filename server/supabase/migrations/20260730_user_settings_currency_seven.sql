-- Widen user_settings.currency to the seven currencies the app actually offers.
--
-- The CHECK allowed only EUR/USD/JPY/GBP, but:
--   * src/data/types.ts CurrencyCode        = 7 (adds KRW, AUD, CAD)
--   * user_settings_router.VALID_CURRENCIES = 7 (adds KRW, AUD, CAD)
--   * REGION_DEFAULTS maps korea -> KRW and oceania -> AUD, so the app hands
--     those out as *defaults* on first launch for those regions
--   * docs/store-description.md promises "seven currencies ... you can change
--     them anytime" — an App Store listing claim
--
-- So the handler validated KRW/AUD/CAD as legal, then the INSERT hit the CHECK
-- and raised 23514, which the handler reported as a generic 500 DB_ERROR.
-- Verified on prod 2026-07-30 before this migration:
--   PUT /settings {"currency":"EUR"} -> 200
--   PUT /settings {"currency":"KRW"} -> 500 DB_ERROR
--   PUT /settings {"currency":"AUD"} -> 500 DB_ERROR
--   PUT /settings {"currency":"CAD"} -> 500 DB_ERROR
--
-- Another instance of [[learning_db_constraints_narrower_than_code]]: a CHECK
-- narrower than the code is a silent dead feature. The code's allow-list is the
-- intended contract here, so the constraint moves to match it.
--
-- Safe to apply: user_settings held 2 rows at the time of writing, both 'EUR'.
--
-- NOT changed on purpose: verified_sales.currency has the same 4-value CHECK,
-- but feedback_router.ALLOWED_CURRENCIES is also 4, so code and constraint
-- agree there — no silent failure. That table is empty and
-- miscApi.submitVerifiedSale has zero FE callers, so widening it would be
-- unreachable change. Revisit if verified sales are ever wired to the UI.

BEGIN;

ALTER TABLE public.user_settings
  DROP CONSTRAINT IF EXISTS user_settings_currency_check;

ALTER TABLE public.user_settings
  ADD CONSTRAINT user_settings_currency_check
  CHECK (currency = ANY (ARRAY[
    'EUR'::text, 'USD'::text, 'GBP'::text, 'JPY'::text,
    'KRW'::text, 'AUD'::text, 'CAD'::text
  ]));

COMMIT;
