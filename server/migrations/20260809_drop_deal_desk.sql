-- Remove the Deal Desk: the second of three generations of member-to-member
-- trading, none of which ever carried a real trade.
--
-- WHY IT GOES
-- -----------------------------------------------------------------------------
-- The app grew THREE implementations of the same idea:
--
--   1. `agreements` + `ratings`      — no code at all, 0 rows. Never wired.
--   2. `listings` + `offers` + …     — Deal Desk. Full router, 6 RPCs, 2 screens,
--                                      20 tests. `SELLING_ENABLED=false` since
--                                      it was built. 0 rows in every table.
--   3. `marketplace_listings` +      — P2P. LIVE: 19 listings, 4 offers,
--      `p2p_offers` + `member_grades`  2 grades, E2E-verified against prod.
--
-- Generations 1 and 2 go. Keeping them cost real money in attention: every
-- schema audit, RLS audit, account-deletion audit and orphan-store audit
-- carried entries a reader had to recognise as expected-dead, which is exactly
-- how a gate stops being read. Two of the screens were reachable from Settings
-- and from the item bar, so a user could walk into a subsystem that could not
-- complete a trade.
--
-- WHAT WAS VERIFIED BEFORE DROPPING (2026-08-09, against prod)
-- -----------------------------------------------------------------------------
-- * Row counts, all seven tables:            0
-- * FKs into the set from outside:           ratings -> agreements ONLY, and
--                                            `ratings` is itself in the set
-- * Views depending on the set:              v_offer_summary_v1
-- * Functions referencing the set:           exactly the 6 RPCs below, resolved
--                                            by `oid::regprocedure`, NOT by
--                                            guessed signatures — 13 DROPs in
--                                            the last cleanup were silent
--                                            no-ops because the guesses were
--                                            wrong (a wrong signature makes
--                                            DROP FUNCTION a no-op that still
--                                            reports success)
-- * Triggers:                                t_set_user_id_listings,
--                                            offers_set_updated_at_trg
--
-- SURVIVORS — deliberately NOT touched, and each verified to hold data
-- -----------------------------------------------------------------------------
-- `purchase_mandates` (1 row), `mandate_deals`, `watchlist_items` (13),
-- `alert_trigger_history` (103), `market_hits`, `subscriptions`.
--
-- These matter because `deal_discovery_worker` — which drives **Target Hit**,
-- the paid alerting feature — reads and writes them. The names collide
-- confusingly with Deal Desk ("deal"), and that collision is the whole risk in
-- this migration. The worker was read line by line: it touches
-- alert_trigger_history, mandate_deals, market_hits, subscriptions and
-- watchlist_items, and NONE of the seven tables below. Its only occurrences of
-- the words "offers"/"listings" are prose in a docstring.
--
-- Also surviving: `src/api/dealsApi.ts`'s mandate half and
-- `dealsProvider.toggleForSale`, which look like Deal Desk by filename and are
-- not.

BEGIN;

-- The view first: it depends on both `offers` and `listings`, and dropping it
-- explicitly means the CASCADEs below cannot silently take something nobody
-- enumerated. (Last cleanup, a CASCADE removed a view — v_alerts_pending —
-- that had never been looked for. Enumerating FUNCTIONS is not enumerating
-- DEPENDENTS.)
DROP VIEW IF EXISTS public.v_offer_summary_v1;

-- The 6 Deal Desk RPCs, dropped BY IDENTITY rather than by a written-out
-- signature, so a signature that differs from the one in the docs cannot turn
-- the drop into a no-op.
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT p.oid::regprocedure AS sig
    FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND p.proname IN (
        'rpc_propose_offer_v1', 'rpc_counter_offer_v1', 'rpc_respond_offer_v1',
        'rpc_cancel_offer_v1',  'rpc_mark_shipped_v1',  'rpc_complete_deal_v1'
      )
  LOOP
    RAISE NOTICE 'dropping %', r.sig;
    EXECUTE format('DROP FUNCTION IF EXISTS %s CASCADE', r.sig);
  END LOOP;
END $$;

-- Children before parents, so CASCADE has nothing left to reach for.
DROP TABLE IF EXISTS public.offer_evidence CASCADE;
DROP TABLE IF EXISTS public.offer_events   CASCADE;
DROP TABLE IF EXISTS public.deal_ratings   CASCADE;
DROP TABLE IF EXISTS public.offers         CASCADE;
DROP TABLE IF EXISTS public.listings       CASCADE;

-- Generation 1. `ratings` FKs into `agreements`, so it must precede it. Both
-- are 0 rows and neither has ever had a line of application code — the only
-- mention anywhere was an annotation in audit_rls_coverage.py explaining why
-- they were expected to be empty.
DROP TABLE IF EXISTS public.ratings    CASCADE;
DROP TABLE IF EXISTS public.agreements CASCADE;

COMMIT;
