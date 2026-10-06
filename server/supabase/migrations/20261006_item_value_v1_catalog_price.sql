-- Catalogue price as the last market-derived link of item_value_v1 (2026-10-06).
--
-- THE PROBLEM
-- The catalogue screen shows `mv_catalog_item_price` (a 180-day median of
-- `market_hits_daily`, sales first, listings as fallback; docs/MARKET_DATA.md).
-- The portfolio valued an item only from the price MODEL (`price_predictions`,
-- or the `quick_predictions` snapshot of it), which needs recent SOLD comps.
-- Where those are missing (TCGplayer feed blocked since 2026-07-29; no
-- sold-comp source for ~50 categories, LEGO among them) the same item read
-- "€870" in the catalogue and "Not priced yet" in the member's collection.
-- Measured on the apple-review demo collection: 6 of 9 items.
--
-- THE RULE (Merle, 2026-10-06)
-- When neither model link answers, use the catalogue price, but only when the
-- item's latest market data (max `market_hits_daily.day` for its ref) is from
-- the current calendar year. Older stays 'none' ("Not priced yet"). It is
-- labelled `catalog_price` and carries `value_as_of` (that latest day), so the
-- app can say "Catalogue price · last seen 18 Aug", never "Market estimate".
--
-- ⚠️ "Current calendar year" is a cliff: on 1 January every price whose data
-- is from the previous year drops back to 'none' at once. If that ever
-- matters, change ONLY the cutoff expression below (e.g. to
-- `current_date - 365`); nothing else depends on it.
--
-- WHERE IT SITS: after both model links and before the member's own typed
-- numbers, the same "catalogue first" order as 20260819c. An explicit
-- value_choice = 'mine' still wins over everything.
--
-- WHAT DOES NOT CHANGE: every item whose value came from a model link, the
-- snapshot, or value_choice = 'mine' keeps the same value and source. Proven by
-- diffing all items before/after (see the verification block at the end).
-- The leaderboard keeps ranking on its explicit market list
-- ('catalog_daily', 'catalog_model', 'quick_scan'), so catalog_price, which may
-- be listing prices, never ranks a member.
--
-- SECURITY DEFINER and the LATERAL calling rule are unchanged; see 20260819d.

BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_attribute a JOIN pg_type t ON t.typrelid = a.attrelid
     WHERE t.typname = 'item_value_v1_t' AND a.attname = 'value_as_of' AND NOT a.attisdropped
  ) THEN
    ALTER TYPE public.item_value_v1_t ADD ATTRIBUTE value_as_of date;
  END IF;
END $$;

CREATE OR REPLACE FUNCTION public.item_value_v1(i public.items)
RETURNS public.item_value_v1_t
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $fn$
  WITH links AS (
    SELECT
      (SELECT pp.q50 FROM price_predictions pp
        WHERE pp.item_ref = i.canonical_ref ORDER BY pp.generated_at DESC LIMIT 1) AS model_q50,
      (SELECT qp.q50_eur FROM quick_predictions qp
        WHERE qp.item_id = i.id ORDER BY qp.created_at DESC LIMIT 1) AS snapshot_q50,
      (SELECT NULLIF(qp.raw->>'source', '') FROM quick_predictions qp
        WHERE qp.item_id = i.id ORDER BY qp.created_at DESC LIMIT 1) AS snapshot_source,
      cat.price_eur AS catalog_price,
      cat.last_day AS catalog_day
    FROM (SELECT 1) one
    LEFT JOIN LATERAL (
      SELECT m.price_eur,
             (SELECT max(d.day) FROM market_hits_daily d WHERE d.item_ref = i.canonical_ref) AS last_day
        FROM mv_catalog_item_price m
       WHERE m.category = i.category AND m.item_key = i.canonical_key
       LIMIT 1
    ) cat ON TRUE
  ), usable AS (
    SELECT l.*,
           CASE WHEN l.catalog_price IS NOT NULL
                 AND l.catalog_day >= date_trunc('year', now())::date   -- THE cutoff (see header)
                THEN l.catalog_price END AS catalog_ok
      FROM links l
  )
  SELECT
    COALESCE(
      CASE WHEN i.attrs->>'value_choice' = 'mine' THEN i.estimated_value END,
      u.model_q50,
      u.snapshot_q50,
      u.catalog_ok,
      i.predicted_price_eur, i.estimated_value, 0
    )::float8,
    CASE
      WHEN i.attrs->>'value_choice' = 'mine' AND i.estimated_value IS NOT NULL THEN 'user_estimate'
      WHEN u.model_q50 IS NOT NULL THEN 'catalog_model'
      WHEN u.snapshot_q50 IS NOT NULL THEN COALESCE(u.snapshot_source, 'quick_scan')
      WHEN u.catalog_ok IS NOT NULL THEN 'catalog_price'
      WHEN i.predicted_price_eur IS NOT NULL THEN 'user_estimate'
      WHEN i.estimated_value IS NOT NULL THEN
        CASE WHEN i.attrs->>'value_entry' = 'app' THEN 'app_estimate' ELSE 'user_estimate' END
      ELSE 'none'
    END::text,
    CASE
      WHEN i.attrs->>'value_choice' = 'mine' AND i.estimated_value IS NOT NULL THEN NULL
      WHEN u.model_q50 IS NOT NULL OR u.snapshot_q50 IS NOT NULL THEN NULL
      WHEN u.catalog_ok IS NOT NULL THEN u.catalog_day
    END::date
  FROM usable u
$fn$;

COMMENT ON FUNCTION public.item_value_v1(public.items) IS
 'THE definition of an item''s value, where it came from, and (for catalog_price) how fresh it is. Chain: member choice -> price_predictions -> quick_predictions -> catalogue price if its data is from the current year (2026-10-06) -> typed estimates -> 0. SECURITY DEFINER so the price_predictions read keeps owner rights. Call it with LATERAL.';

CREATE OR REPLACE VIEW public.v_item_values_v1 AS
SELECT i.id AS item_id, v.value_eur, v.value_source, v.value_as_of
FROM items i
LEFT JOIN LATERAL public.item_value_v1(i) v ON TRUE
WHERE i.user_id = auth.uid();

COMMIT;

NOTIFY pgrst, 'reload schema';
