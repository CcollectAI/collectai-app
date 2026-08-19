-- v_item_values_v1 gains `value_source`: WHERE the number came from.
--
-- The value chain has always been four links deep, and the app rendered all
-- four identically. A EUR 185 backed by twelve sold comps and a EUR 185 someone
-- typed into a text field are the same pixels today. That matters most where it
-- is least visible: measured 2026-08-19, `category_items.set_name`-carrying TCG
-- categories aside, ~62,000 catalogue items have NO sold-comp source at all, so
-- for whole categories — watches, whiskey, LEGO, Warhammer — the displayed
-- "value" IS the member's own guess wearing the app's authority.
--
-- No new storage, no backfill, nothing to maintain: this is the same CASE the
-- COALESCE already walks, returning the label of whichever link answered.
--
-- ── The labels, and why they are not what you would guess ────────────────────
--
-- `quick_predictions` is NOT QuickScan output, despite the name and despite
-- docs/ARCHITECTURE.md saying so (corrected 2026-08-19). It has exactly ONE
-- writer — `write_quick_valuation` (items_router.py), which reads
-- `price_prediction_daily.q50` and stamps `raw.source = 'catalog_daily'`. It is
-- therefore COMP-BACKED, and labelling it "quick scan" would understate it.
--
-- QuickScan's vision estimate lands in `items.estimated_value`, alongside
-- hand-typed guesses and CSV-imported ones — so distinguishing "app estimate"
-- from "your estimate" needs the WRITER to stamp which
-- (`items.attrs->>'value_entry'`); the column alone cannot tell them apart.
-- Links 3 AND 4 are both unbacked; only links 1 and 2 rest on comps.
--
--   catalog_daily  — quick_predictions row from the daily catalogue rollup
--   quick_scan     — a quick_predictions row from any other writer (none today)
--   catalog_model  — price_predictions.q50, joined by items.canonical_ref
--   user_estimate  — a number a member supplied (see the trap below)
--   app_estimate   — estimated_value written by a scan (attrs.value_entry='app')
--   none           — we do not know, and the value is 0
--
-- ⚠️ THE COLUMN NAMES LIE, so read this before touching the CASE.
-- `items.predicted_price_eur` sounds like model output. It has exactly ONE
-- writer in the entire codebase — `app/add-manual.tsx`, the "Estimated value"
-- text field — so link 3 is the MEMBER'S OWN TYPED NUMBER, not a prediction.
-- Labelling it `model_stored` (as the first draft of this migration did) would
-- have published a hand-typed guess as a model figure, which is the exact
-- confusion this column is meant to end.
--
-- `items.estimated_value` (link 4) is written by `POST /items` and by the CSV
-- importer. `POST /items` does not set `items.source`, so the column cannot say
-- whether a human or a vision scan produced the number — hence the
-- `attrs.value_entry` stamp, written by the QuickScan draft path.
--
-- `catalog_daily`, `quick_scan` and `catalog_model` are comp/model-backed;
-- `user_estimate` and `app_estimate` are not. That boundary is
-- what the leaderboard filters on (market truth only, decided 2026-08-19) and
-- what the portfolio marks rather than hides (include-and-mark).
--
-- CHAIN ORDER IS UNCHANGED, deliberately. This migration must not move a single
-- number already on screen; it only says where each number came from. The
-- COALESCE below is byte-for-byte the one adopted 2026-08-11 after being
-- EXCEPT-diffed in both directions against both live server expressions.
--
-- AFTER APPLYING: regenerate scripts/schema.lock.json — the view is locked with
-- its column list and a stale lock only bites on the NEXT bake restart, hours
-- after this change, looking like unrelated drift
-- (learning_stale_schema_lock_is_a_restart_time_bomb).

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
  )::float8 AS value_eur,
  CASE
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
    -- Single writer: add-manual's "Estimated value" field. A member's number.
    WHEN i.predicted_price_eur IS NOT NULL THEN 'user_estimate'
    WHEN i.estimated_value IS NOT NULL THEN
      -- Stamped by the writer at insert; absent on every row written before
      -- 2026-08-19, which is why the fallback is the conservative one. Calling
      -- a scan's number "your estimate" is a smaller lie than calling a typed
      -- guess "the app's".
      CASE WHEN i.attrs->>'value_entry' = 'app' THEN 'app_estimate'
           ELSE 'user_estimate' END
    ELSE 'none'
  END::text AS value_source
FROM items i
WHERE i.user_id = auth.uid();

COMMENT ON VIEW public.v_item_values_v1 IS
 'Canonical per-item value AND its provenance. Runs as owner so it can read price_predictions (RLS deny_all); scoped by auth.uid(). value_source: catalog_daily|quick_scan|catalog_model|user_estimate|app_estimate|none — everything above app_estimate is comp/model-backed. See docs/ARCHITECTURE.md value-sources.';

GRANT SELECT ON public.v_item_values_v1 TO authenticated;

COMMIT;

-- PostgREST caches the schema; without this the new column is invisible to the
-- app until the next reload.
NOTIFY pgrst, 'reload schema';
