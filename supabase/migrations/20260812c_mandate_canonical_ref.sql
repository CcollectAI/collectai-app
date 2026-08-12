-- purchase_mandates.canonical_ref — value a mandate against a KNOWN item.
--
-- Today `_get_prediction(conn, query, category)` is keyed on the mandate's
-- SEARCH STRING and matches with `item_ref ILIKE`, so every deal a mandate
-- produces inherits one prediction for the whole query. Measured 2026-08-12 on
-- a live "charizard"/pokemon mandate: 27 deals sharing q50 EUR 1.08 / q90
-- EUR 21.79, against listings from EUR 2.59 to EUR 216.54. That is a category
-- average, not the value of anything anyone bought — which is why
-- `value_summary_router.deal_savings` cannot honestly report a number from it.
--
-- The fix is not to guess a listing's identity. `docs/MARKET_DATA.md` records
-- that keyword matching of marketplace titles was measured and rejected
-- ("costs all of the yield for none of the precision"), and eBay's structured
-- catalogue (EPID) is not surfaced by our adapter. So instead of inferring what
-- a listing IS, let the mandate say what it is SHOPPING FOR: the user picks a
-- catalogue item, and the prediction becomes per-item.
--
-- ONE COLUMN, NAMESPACED. `items` carries both `canonical_key` (bare) and
-- `canonical_ref` (namespaced) because it joins the catalogue on the bare form
-- AND predictions on the namespaced one. A mandate only ever joins
-- `price_predictions.item_ref`, which is namespaced always (0 bare rows in
-- 1.7M — CLAUDE.md "Identifier formats"). Storing only the joinable form means
-- there is no second copy to drift, and no trigger to maintain it. The API
-- namespaces a bare key at the boundary, deriving the prefix from the item's
-- OWN category in `category_items`, because a ref built from the wrong
-- namespace matches zero prediction rows and fails SILENTLY — that is exactly
-- the 2026-07-25 bug that emptied 44 join sites for four months.
--
-- NULLABLE ON PURPOSE. Every existing mandate is text-only and keeps working:
-- the agent falls back to the ILIKE path when this is NULL, and deal_savings
-- counts only deals whose mandate is keyed. Nothing is backfilled, because
-- there is no honest way to infer the key for an existing free-text mandate.
--
-- No index: `purchase_mandates` is tiny (Pro caps at 10 per user) and this
-- column is read per-scan off a row already fetched by primary key. Governance
-- rule 1 in docs/DATA_SCALING_PLAN.md is "default = refuse to add".

ALTER TABLE public.purchase_mandates
    ADD COLUMN IF NOT EXISTS canonical_ref text;

COMMENT ON COLUMN public.purchase_mandates.canonical_ref IS
    'Namespaced catalogue key (category:bare_key) this mandate values against, '
    'matching price_predictions.item_ref exactly. NULL = free-text mandate, '
    'valued by the legacy ILIKE-on-search_query path and excluded from '
    'value_summary deal_savings. Written by the API from a bare canonical_key; '
    'never set this by hand.';
