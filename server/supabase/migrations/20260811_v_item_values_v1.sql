-- One definition of "what is this item worth", readable by the app.
--
-- Measured on prod 2026-08-11: the app derived an item's value itself as
-- `quick_predictions -> predicted_price_eur -> estimated_value`, while every
-- server surface used `quick_predictions -> price_predictions ->
-- predicted_price_eur -> estimated_value`. The missing middle link — the
-- catalog model — meant an item priced only by that model read EUR 0 in the
-- app while the server held a value for it: 15 of 34 active items, 44%.
--
-- Per category the two were far enough apart to be visible together:
--
--   category        tile said   list summed to
--   one_piece_tcg      80.64             0.00
--   pokemon            55.57            15.00
--   yugioh              1.10             0.05
--
-- Nothing errored and nothing could: an item priced at 0 is a valid item. The
-- two numbers simply lived on two screens that never appeared side by side.
-- Making the Portfolio category tiles pressable puts them one tap apart, which
-- is what forced this.
--
-- WHY A VIEW AND NOT A CLIENT-SIDE JOIN: `price_predictions` carries an RLS
-- policy `price_predictions_deny_all` (`USING (false)`) while SELECT is granted
-- to `authenticated`. A direct read from the app therefore SUCCEEDS and returns
-- an empty set — a fix that changes nothing and reports no error. The deny-all
-- is deliberate (catalog-model output is not user-scoped data) and stays.
--
-- A view resolves that without weakening it: it executes with its OWNER's
-- rights, so it can read the valuation table, and it filters
-- `i.user_id = auth.uid()`, so a caller sees only their own items. Verified as
-- the `authenticated` role before adoption: 0 rows from `price_predictions`
-- directly, 8 rows through the view, 0 rows belonging to any other user.
--
-- WHY A VIEW AND NOT A DENORMALISED COLUMN: a column needs a backfill, a
-- trigger or worker to maintain it, and a write-path benchmark (governance rule
-- 2, docs/DATA_SCALING_PLAN.md §6) — and it can go stale. A view stores
-- nothing, cannot drift from its inputs, and is derived fresh per read.
--
-- CHAIN ORDER matches /analytics/portfolio/category-breakdown
-- (quick -> catalog -> stored), NOT /portfolio/items (catalog -> quick ->
-- stored). Those two server endpoints disagree on the order today; the
-- breakdown's is the number the Portfolio tile shows, which is what a user is
-- comparing against when they tap into a category. Only 2 items currently have
-- both sources and they agree, so the divergence is latent, not live — repoint
-- both endpoints at this view and it stops being possible.
--
-- PROVEN EQUIVALENT BEFORE ADOPTION: EXCEPT-diffed in both directions against
-- BOTH live server expressions, under a real `request.jwt.claim.sub` context.
-- All four counts were 0, so switching to it could not move a number already on
-- screen.
--
-- COST: ~0.55ms per item warm (EXPLAIN ANALYZE), using the per-partition
-- `price_predictions_*_item_ref_idx` indexes; a 20-item page costs ~11ms. The
-- app reads it bounded by the page's ids, never the whole collection.
--
-- NO `archived` FILTER ON PURPOSE: callers decide, so /archived can use it too.

BEGIN;

CREATE OR REPLACE VIEW public.v_item_values_v1 AS
SELECT
  i.id AS item_id,
  COALESCE(
    (SELECT qp.q50_eur FROM quick_predictions qp
      WHERE qp.item_id = i.id ORDER BY qp.created_at DESC LIMIT 1),
    (SELECT pp.q50 FROM price_predictions pp
      WHERE pp.item_ref = i.canonical_ref ORDER BY pp.generated_at DESC LIMIT 1),
    i.predicted_price_eur, i.estimated_value, 0
  )::float8 AS value_eur
FROM items i
WHERE i.user_id = auth.uid();

COMMENT ON VIEW public.v_item_values_v1 IS
 'Canonical per-item value. Runs as owner so it can read price_predictions (RLS deny_all); scoped by auth.uid() so a caller sees only their own items. See docs/ARCHITECTURE.md value-sources.';

GRANT SELECT ON public.v_item_values_v1 TO authenticated;

COMMIT;

-- PostgREST caches the schema; without this the view 404s from the app until
-- the next reload.
NOTIFY pgrst, 'reload schema';
