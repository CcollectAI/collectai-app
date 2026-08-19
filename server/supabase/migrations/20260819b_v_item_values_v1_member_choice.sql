-- v_item_values_v1: an explicit member choice outranks the model.
--
-- WHY THIS EXISTS
-- Manual add already offers to price the item for you: it saves what you typed,
-- then fires `revalueItem`, which writes a catalogue-derived valuation into
-- `quick_predictions` — link 1, the TOP of the chain. So a catalogue-linked
-- item silently starts showing our number while the member's own figure sits in
-- `estimated_value`, never displayed. Nobody was asked, and nothing said it had
-- happened.
--
-- The app now asks ("we found a market comp — use it, or keep yours?"), and a
-- question is only honest if BOTH answers are possible. Without this branch,
-- "keep mine" could not be honoured: `quick_predictions` and
-- `price_predictions` both outrank `estimated_value`, and neither can be
-- deleted to get out of the way — the catalogue model is global data, not this
-- member's row.
--
-- So the choice goes at the TOP, above the model, and only when the member has
-- explicitly made it. `attrs.value_choice = 'mine'`, written by the item screen
-- when they answer. Absent on every row that has not been asked, which is all
-- of them today, so this migration cannot move a number that nobody chose.
--
-- WHAT IT IS NOT
-- Not a way to inflate anything public: the leaderboard ranks on the
-- market-backed sources only, and a chosen number reports as `user_estimate`,
-- which the board excludes. This changes what the MEMBER sees about their OWN
-- collection — which is exactly the scope Merle set for member-supplied prices.
--
-- REVERSIBLE: re-run 20260819_v_item_values_v1_value_source.sql to drop the
-- branch. Applying it does not change any stored data.
--
-- AFTER APPLYING: regenerate scripts/schema.lock.json and DIFF it. The view is
-- locked by column list; the column list is unchanged here, but a regen is the
-- only way to know that rather than assume it
-- (learning_stale_schema_lock_is_a_restart_time_bomb).

BEGIN;

CREATE OR REPLACE VIEW public.v_item_values_v1 AS
SELECT
  i.id AS item_id,
  COALESCE(
    -- The member was asked and said "keep mine". Above the model on purpose.
    CASE WHEN i.attrs->>'value_choice' = 'mine' THEN i.estimated_value END,
    (SELECT qp.q50_eur FROM quick_predictions qp
      WHERE qp.item_id = i.id ORDER BY qp.created_at DESC LIMIT 1),
    (SELECT pp.q50 FROM price_predictions pp
      WHERE pp.item_ref = i.canonical_ref ORDER BY pp.generated_at DESC LIMIT 1),
    i.predicted_price_eur, i.estimated_value, 0
  )::float8 AS value_eur,
  CASE
    -- Same branch, same order, so the label can never disagree with the value.
    WHEN i.attrs->>'value_choice' = 'mine' AND i.estimated_value IS NOT NULL
      THEN 'user_estimate'
    WHEN (SELECT qp.q50_eur FROM quick_predictions qp
           WHERE qp.item_id = i.id ORDER BY qp.created_at DESC LIMIT 1) IS NOT NULL
      THEN COALESCE(
             (SELECT NULLIF(qp.raw->>'source', '') FROM quick_predictions qp
               WHERE qp.item_id = i.id ORDER BY qp.created_at DESC LIMIT 1),
             'quick_scan')
    WHEN (SELECT pp.q50 FROM price_predictions pp
           WHERE pp.item_ref = i.canonical_ref
        ORDER BY pp.generated_at DESC LIMIT 1) IS NOT NULL
      THEN 'catalog_model'
    WHEN i.predicted_price_eur IS NOT NULL THEN 'user_estimate'
    WHEN i.estimated_value IS NOT NULL THEN
      CASE WHEN i.attrs->>'value_entry' = 'app' THEN 'app_estimate'
           ELSE 'user_estimate' END
    ELSE 'none'
  END::text AS value_source
FROM items i
WHERE i.user_id = auth.uid();

COMMENT ON VIEW public.v_item_values_v1 IS
 'Canonical per-item value AND its provenance. An explicit attrs.value_choice=''mine'' outranks the model; otherwise quick_predictions -> price_predictions -> predicted_price_eur -> estimated_value. Runs as owner so it can read price_predictions (RLS deny_all); scoped by auth.uid(). value_source: catalog_daily|quick_scan|catalog_model|user_estimate|app_estimate|none. See docs/ARCHITECTURE.md value-sources.';

GRANT SELECT ON public.v_item_values_v1 TO authenticated;

COMMIT;

NOTIFY pgrst, 'reload schema';
