-- v_item_values_v1: the LIVE catalogue price outranks the frozen snapshot.
--
-- WHAT THE TWO SOURCES ACTUALLY ARE
--   `price_predictions.q50`  — the catalogue model's CURRENT output, joined by
--                              items.canonical_ref, recomputed as sales arrive.
--   `quick_predictions.q50_eur` — a COPY of `price_prediction_daily.q50` frozen
--                              into the row by `write_quick_valuation` at the
--                              moment the item was added or revalued.
--
-- Both are comp-backed, so this is not a trust question; it is a FRESHNESS
-- question. Until now the view preferred the snapshot, which means an item
-- added in July kept quoting July's price for as long as nobody revalued it —
-- while the app labelled that number "Market estimate".
--
-- MEASURED ON PROD BEFORE CHANGING IT (2026-08-19), because this moves real
-- numbers rather than tidying code:
--
--   74 active items · 4 with a snapshot · 11 with a live price · 3 with BOTH
--   ...and 2 of those 3 DISAGREE:
--
--     yugioh  "Test"              snapshot 0.05 (2026-07-28)  live 0.04 (2026-08-19)
--     pokemon "Rocket's Scyther"  snapshot 34.43 (2026-08-15) live 34.50 (2026-08-18)
--
--   In both cases the live price is NEWER, which is the pattern the design
--   predicts: a snapshot can only age.
--
-- docs/ARCHITECTURE.md described this divergence as "latent, not live — only 2
-- items have both and they agree". That was true when written and is no longer;
-- the doc is corrected alongside this migration.
--
-- WHY THE VIEW MOVES RATHER THAN THE ENDPOINTS
-- `/portfolio/items` and `/portfolio/overview` already order catalogue-first.
-- Making the view match them means ONE order across the app, and it is the
-- order that keeps "Market estimate" meaning the current market rather than
-- whenever the member happened to add the item.
--
-- The member's explicit choice still outranks everything: `value_choice='mine'`
-- stays at the top (20260819b).
--
-- AFTER APPLYING: regenerate scripts/schema.lock.json and diff. Column list is
-- unchanged, but a regen is the only way to know that rather than assume it.

BEGIN;

CREATE OR REPLACE VIEW public.v_item_values_v1 AS
SELECT
  i.id AS item_id,
  COALESCE(
    CASE WHEN i.attrs->>'value_choice' = 'mine' THEN i.estimated_value END,
    -- LIVE catalogue price first (2026-08-19).
    (SELECT pp.q50 FROM price_predictions pp
      WHERE pp.item_ref = i.canonical_ref ORDER BY pp.generated_at DESC LIMIT 1),
    -- Then the frozen snapshot, for items the catalogue model has not priced.
    (SELECT qp.q50_eur FROM quick_predictions qp
      WHERE qp.item_id = i.id ORDER BY qp.created_at DESC LIMIT 1),
    i.predicted_price_eur, i.estimated_value, 0
  )::float8 AS value_eur,
  CASE
    WHEN i.attrs->>'value_choice' = 'mine' AND i.estimated_value IS NOT NULL
      THEN 'user_estimate'
    WHEN (SELECT pp.q50 FROM price_predictions pp
           WHERE pp.item_ref = i.canonical_ref
        ORDER BY pp.generated_at DESC LIMIT 1) IS NOT NULL
      THEN 'catalog_model'
    WHEN (SELECT qp.q50_eur FROM quick_predictions qp
           WHERE qp.item_id = i.id ORDER BY qp.created_at DESC LIMIT 1) IS NOT NULL
      THEN COALESCE(
             (SELECT NULLIF(qp.raw->>'source', '') FROM quick_predictions qp
               WHERE qp.item_id = i.id ORDER BY qp.created_at DESC LIMIT 1),
             'quick_scan')
    WHEN i.predicted_price_eur IS NOT NULL THEN 'user_estimate'
    WHEN i.estimated_value IS NOT NULL THEN
      CASE WHEN i.attrs->>'value_entry' = 'app' THEN 'app_estimate'
           ELSE 'user_estimate' END
    ELSE 'none'
  END::text AS value_source
FROM items i
WHERE i.user_id = auth.uid();

COMMENT ON VIEW public.v_item_values_v1 IS
 'Canonical per-item value AND its provenance. Order: member choice (attrs.value_choice=''mine'') -> LIVE catalogue price (price_predictions) -> frozen snapshot (quick_predictions) -> predicted_price_eur -> estimated_value. Runs as owner so it can read price_predictions (RLS deny_all); scoped by auth.uid(). See docs/ARCHITECTURE.md value-sources.';

GRANT SELECT ON public.v_item_values_v1 TO authenticated;

COMMIT;

NOTIFY pgrst, 'reload schema';
