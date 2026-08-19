-- ONE definition of item value, callable from both sides. (Stage 2)
--
-- THE PROBLEM THIS CLOSES
-- The chain existed in FIVE places: `v_item_values_v1`, `/portfolio/items`,
-- `/portfolio/overview`, `/analytics/portfolio/category-breakdown` and the
-- leaderboard. They were made to agree on 2026-08-19 and are held there by
-- `test_leaderboard_value_parity.py` and `e2e_value_provenance.py` — but
-- agreement maintained by tests is not the same as one definition, and this
-- chain has drifted twice already (the missing catalogue link on 2026-08-17,
-- the snapshot-vs-live order on 2026-08-19).
--
-- The obvious fix — "have the routers select from the view" — is impossible:
-- the view ends `WHERE i.user_id = auth.uid()` and the server's pool has no
-- auth context. That is precisely why the chain was copied in the first place.
-- A FUNCTION has no such scoping, so both sides can call it.
--
-- ⚠️ SECURITY DEFINER IS LOAD-BEARING, NOT DECORATION.
-- `price_predictions` grants SELECT to `authenticated` and denies every row via
-- RLS (`price_predictions_deny_all`). The view can read it only because a view
-- executes with its OWNER's rights. Moving that read into a SECURITY INVOKER
-- function would re-check it as the CALLER — and the failure would be silent:
-- the query succeeds and returns an empty set, so every catalogue-priced item
-- would quietly fall through to the member's own estimate. Same trap the view's
-- own comment warns about. Owned by `postgres`, the view's owner, with
-- search_path pinned so the definer rights cannot be redirected.
--
-- ⚠️ CALL IT VIA LATERAL, NEVER `(f(i)).*`.
-- Postgres expands `(f(i)).a, (f(i)).b` into TWO calls, so a composite-returning
-- function written that way doubles every subquery inside it. `LEFT JOIN
-- LATERAL f(i) v ON TRUE` evaluates it once per row.
--
-- The body is the chain as of 20260819c, moved verbatim. This migration must
-- not move a single number: it is proven by EXCEPT-diffing the view against its
-- previous definition in both directions, as the `authenticated` role.

BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
                  WHERE n.nspname = 'public' AND t.typname = 'item_value_v1_t') THEN
    CREATE TYPE public.item_value_v1_t AS (value_eur float8, value_source text);
  END IF;
END $$;

CREATE OR REPLACE FUNCTION public.item_value_v1(i public.items)
RETURNS public.item_value_v1_t
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $fn$
  SELECT
    COALESCE(
      CASE WHEN i.attrs->>'value_choice' = 'mine' THEN i.estimated_value END,
      (SELECT pp.q50 FROM price_predictions pp
        WHERE pp.item_ref = i.canonical_ref ORDER BY pp.generated_at DESC LIMIT 1),
      (SELECT qp.q50_eur FROM quick_predictions qp
        WHERE qp.item_id = i.id ORDER BY qp.created_at DESC LIMIT 1),
      i.predicted_price_eur, i.estimated_value, 0
    )::float8,
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
    END::text
$fn$;

COMMENT ON FUNCTION public.item_value_v1(public.items) IS
 'THE definition of an item''s value and where it came from. Called by v_item_values_v1 and by the server routers, which cannot read the view (it is auth.uid()-scoped and the pool has no auth context). SECURITY DEFINER so the price_predictions read keeps the owner rights the view relied on — as INVOKER, RLS would return an empty set and every catalogue-priced item would silently fall back to the member''s estimate. Call it with LATERAL: (f(i)).a, (f(i)).b evaluates it twice.';

-- `authenticated` calls it only THROUGH the view today, but granting execute
-- keeps the function usable from PostgREST if a future screen needs it, and
-- costs nothing: the definer rights are what gate the underlying table, not
-- this grant.
GRANT EXECUTE ON FUNCTION public.item_value_v1(public.items) TO authenticated;

CREATE OR REPLACE VIEW public.v_item_values_v1 AS
SELECT i.id AS item_id, v.value_eur, v.value_source
FROM items i
LEFT JOIN LATERAL public.item_value_v1(i) v ON TRUE
WHERE i.user_id = auth.uid();

COMMENT ON VIEW public.v_item_values_v1 IS
 'Canonical per-item value + provenance for the CURRENT member. Thin wrapper over public.item_value_v1(items), which is the single definition the server routers also call. Scoped by auth.uid(). See docs/ARCHITECTURE.md value-sources.';

GRANT SELECT ON public.v_item_values_v1 TO authenticated;

COMMIT;

NOTIFY pgrst, 'reload schema';
