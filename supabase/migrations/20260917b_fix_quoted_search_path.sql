-- 2026-09-17: undo a search_path that names ONE schema called "public, pg_temp".
--
-- WHAT WENT WRONG
-- 20260424_security_advisor_bulk_C_and_A.sql pinned search_path on every
-- function that had none, with
--     EXECUTE format('ALTER FUNCTION %s SET search_path = %L', f.sig, 'public, pg_temp');
-- %L quotes its argument as ONE literal, so Postgres stored
--     search_path="public, pg_temp"
-- — a single schema whose name contains a comma. That schema does not exist,
-- so inside those functions nothing resolves except pg_catalog. Functions that
-- write `public.x` kept working; every unqualified table or function reference
-- fails with 42P01 / 42883. The migration's own comment says the intent was the
-- opposite ("doesn't force fully-qualified refs in body"). Three later files
-- copied the same quoted spelling by hand (20260424_partition_price_history,
-- 20260424_partition_price_predictions, 20260814g_fix_refresh_core_mvs).
--
-- WHAT IT BROKE (verified on production 2026-09-17, read-only):
--   * rpc_list_blocked_v1  → ERROR relation "user_blocks" does not exist
--     (Settings → Blocked users has been a failed state for every member)
--   * rpc_is_blocked_v1    → same error; the app turned it into "not blocked"
--   * rpc_block_user_v1    → plpgsql_check: "user_blocks", "chat_threads" do
--     not exist — blocking cannot be done at all
-- 203 functions in `public` carried the quoted form (124 plpgsql, 55 SQL, 24
-- trigger functions; counted read-only 2026-09-17). Most are fully qualified
-- and unaffected; this does not list them one by one, because the fix is the
-- same for all of them and is a no-op for the qualified ones.
--
-- THE FIX
-- Re-pin the path UNQUOTED on exactly the functions that carry the broken
-- value. Metadata only: no body changes, no table locks, and a function that
-- only uses qualified names resolves identically before and after. Note this
-- makes previously-FAILING functions work — for blocking that is the point;
-- review any worker function that has been silently failing before applying.
--
-- `pg_temp` stays LAST, which is what keeps search_path injection closed.
--
-- NOT fixed here: a function that calls an extension function living in the
-- `extensions` schema (rpc_enqueue_push_v1 → digest()) still will not find it
-- on `public, pg_temp`. That was broken before this file and is not changed by it.
--
-- Gate: scripts/check-sql-search-path.mjs (in verify:prebuild).

BEGIN;

DO $$
DECLARE
  f record;
  v_count int := 0;
BEGIN
  FOR f IN
    SELECT p.oid::regprocedure AS sig, p.prokind
    FROM pg_proc p
    JOIN pg_namespace ns ON ns.oid = p.pronamespace
    WHERE ns.nspname = 'public'
      AND EXISTS (
        SELECT 1 FROM unnest(p.proconfig) cfg
        WHERE cfg = 'search_path="public, pg_temp"'
      )
  LOOP
    -- NO %L here. That is the whole bug: the path list must be SQL, not a literal.
    EXECUTE format(
      'ALTER %s %s SET search_path = public, pg_temp',
      CASE f.prokind WHEN 'p' THEN 'PROCEDURE' ELSE 'FUNCTION' END,
      f.sig
    );
    v_count := v_count + 1;
  END LOOP;
  RAISE NOTICE 'Re-pinned search_path on % functions', v_count;
END $$;

-- Refuse to commit if a quoted multi-schema path survives in `public` in any
-- spelling the loop above did not know (e.g. "public, extensions"). Scoped to
-- `public` like the loop; a hit means: read those functions, do not widen blindly.
DO $$
DECLARE
  v_left int;
BEGIN
  SELECT count(*) INTO v_left
  FROM pg_proc p
  JOIN pg_namespace ns ON ns.oid = p.pronamespace
  CROSS JOIN LATERAL unnest(p.proconfig) cfg
  WHERE ns.nspname = 'public'
    AND cfg LIKE 'search_path=%"%,%"%';
  IF v_left > 0 THEN
    RAISE EXCEPTION '% public function(s) still carry a quoted multi-schema search_path', v_left;
  END IF;
END $$;

COMMIT;
