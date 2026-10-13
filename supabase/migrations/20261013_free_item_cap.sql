-- Free plan: at most 100 active items in a collection (2026-10-13).
--
-- Decision: docs/OPEN_DECISIONS.md -> Decided 2026-10-13 (Pricing, point 2). Scans
-- stay free; the 101st active item is refused with PLAN_LIMIT_ITEMS and the app
-- turns that into a Pro offer (src/lib/planLimitPrompt.ts).
--
-- WHY A TRIGGER and not a check in each endpoint: items are created by SIX
-- writers -- POST /items, /intake/save, CSV import, a marketplace-only listing,
-- trade settlement, and app/add-manual.tsx which inserts through supabase-js
-- straight past the API. A per-endpoint check would always miss one; this is
-- the single chokepoint every one of them passes.
--
-- Plan resolution mirrors app/subscription.py::get_user_plan: Pro/Premium =
-- a subscriptions row with plan in (pro, premium) and status in (active,
-- trialing). Anything else is free.
--
-- Exemption: trade settlement (p2p_offers_router._settle_completed_trade)
-- runs `SELECT set_config('app.skip_item_cap', 'on', true)` in its own
-- transaction, so a completed purchase can never fail on the buyer's cap.
-- The setting is transaction-local; PostgREST exposes no way to set it.
--
-- Soft cap: two concurrent inserts at 99 can both pass. Accepted -- the cap is
-- a nudge, not a quota with money behind it.
--
-- Measured before applying (2026-10-13): 4 members own items, max 9, none at
-- or above 100 -- nobody is affected on day one.

CREATE OR REPLACE FUNCTION public.enforce_free_item_cap()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public', 'pg_temp'
AS $fn$
DECLARE
  v_count integer;
BEGIN
  IF coalesce(NEW.archived, false) THEN
    RETURN NEW;
  END IF;
  IF current_setting('app.skip_item_cap', true) = 'on' THEN
    RETURN NEW;
  END IF;
  IF EXISTS (
    SELECT 1 FROM public.subscriptions s
     WHERE s.user_id = NEW.user_id
       AND s.plan IN ('pro', 'premium')
       AND s.status IN ('active', 'trialing')
  ) THEN
    RETURN NEW;
  END IF;

  SELECT count(*) INTO v_count
    FROM public.items i
   WHERE i.user_id = NEW.user_id
     AND coalesce(i.archived, false) = false;

  IF v_count >= 100 THEN
    RAISE EXCEPTION 'PLAN_LIMIT_ITEMS: the free plan holds 100 items'
      USING ERRCODE = 'P0001',
            HINT = 'Upgrade to Pro for an unlimited collection.';
  END IF;
  RETURN NEW;
END;
$fn$;

REVOKE ALL ON FUNCTION public.enforce_free_item_cap() FROM PUBLIC;
-- Supabase grants EXECUTE to anon/authenticated on new functions by default
-- (seen after the first apply 2026-10-13: has_function_privilege(anon) = t).
-- A trigger function needs no EXECUTE grant to fire, so take it away.
REVOKE ALL ON FUNCTION public.enforce_free_item_cap() FROM anon, authenticated;

DROP TRIGGER IF EXISTS trg_items_free_cap ON public.items;
CREATE TRIGGER trg_items_free_cap
  BEFORE INSERT ON public.items
  FOR EACH ROW EXECUTE FUNCTION public.enforce_free_item_cap();
