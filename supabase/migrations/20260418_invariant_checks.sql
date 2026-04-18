-- R50l hardening: promote runtime invariants into DB constraints so the
-- bugs we fixed this round can never silently regress. Each constraint
-- matches an invariant that runtime code was supposed to guard but didn't.

-- ---------------------------------------------------------------------------
-- 1. attributes_json must always be a JSONB object.
-- ---------------------------------------------------------------------------
-- R50d wrote stringified JSON; R50e || merge wrapped objects in arrays;
-- both went uncaught for months. Every reader expects an object and silently
-- returns NULL on other types. Promote to a hard constraint so future
-- writers cannot regress without getting an immediate Postgres error.
ALTER TABLE public.category_items
    DROP CONSTRAINT IF EXISTS category_items_attrs_is_object;

ALTER TABLE public.category_items
    ADD CONSTRAINT category_items_attrs_is_object
    CHECK (
        attributes_json IS NULL
        OR jsonb_typeof(attributes_json) = 'object'
    ) NOT VALID;

-- Backfill was already done via repair_attributes_json_types.py — mark valid
-- so Postgres enforces the constraint on every future INSERT/UPDATE.
ALTER TABLE public.category_items
    VALIDATE CONSTRAINT category_items_attrs_is_object;

-- ---------------------------------------------------------------------------
-- 2. price_predictions sanity: ordered quantiles + non-negative + ≤ €20M.
-- ---------------------------------------------------------------------------
-- Lego Ridge model output €1,545,759,435 for 65 rows before the R50l clamp
-- landed. Runtime clamp is good; a DB-level constraint means the next broken
-- model fails the insert loudly instead of writing garbage for hours.
ALTER TABLE public.price_predictions
    DROP CONSTRAINT IF EXISTS price_predictions_sanity;

ALTER TABLE public.price_predictions
    ADD CONSTRAINT price_predictions_sanity
    CHECK (
        (q10 IS NULL OR q10 >= 0)
        AND (q50 IS NULL OR q50 >= 0)
        AND (q90 IS NULL OR q90 >= 0)
        AND (q10 IS NULL OR q90 IS NULL OR q10 <= q90)
        AND (q10 IS NULL OR q50 IS NULL OR q10 <= q50)
        AND (q50 IS NULL OR q90 IS NULL OR q50 <= q90)
        AND (q90 IS NULL OR q90 <= 20000000)
    ) NOT VALID;

ALTER TABLE public.price_predictions
    VALIDATE CONSTRAINT price_predictions_sanity;

-- ---------------------------------------------------------------------------
-- 3. market_hits.item_ref must be either NULL or category-prefixed.
-- ---------------------------------------------------------------------------
-- R50l found 153,577 rows missing the `category:` prefix, orphaning predictions
-- for 15 categories. Prefix convention is "category:item_key". Writers that
-- skip the prefix silently break valuation join.
ALTER TABLE public.market_hits
    DROP CONSTRAINT IF EXISTS market_hits_item_ref_prefix;

ALTER TABLE public.market_hits
    ADD CONSTRAINT market_hits_item_ref_prefix
    CHECK (
        item_ref IS NULL
        OR item_ref LIKE '%:%'
    ) NOT VALID;

ALTER TABLE public.market_hits
    VALIDATE CONSTRAINT market_hits_item_ref_prefix;

-- ---------------------------------------------------------------------------
-- 4. market_hits price sanity (upper bound only — zero-price filter is in
--    persist_comps_to_db already).
-- ---------------------------------------------------------------------------
-- Prior incident (learnings #25): Crawl4AI parsed "Site Statistics" as a
-- €1.5B price. A DB cap catches the next variant of that class.
ALTER TABLE public.market_hits
    DROP CONSTRAINT IF EXISTS market_hits_price_sane;

ALTER TABLE public.market_hits
    ADD CONSTRAINT market_hits_price_sane
    CHECK (
        (price IS NULL OR price <= 20000000)
        AND (price_eur IS NULL OR price_eur <= 20000000)
    ) NOT VALID;

ALTER TABLE public.market_hits
    VALIDATE CONSTRAINT market_hits_price_sane;
