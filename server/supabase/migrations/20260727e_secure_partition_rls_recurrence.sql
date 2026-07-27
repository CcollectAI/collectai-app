-- 2026-07-27: stop monthly partitions arriving with RLS disabled.
--
-- Apply with:
--   psql "$DB_DSN_DIRECT" -f 20260727e_secure_partition_rls_recurrence.sql
--
-- WHY
-- ---
-- 20260727_rls_disabled_partitions.sql fixed the two partitions that were
-- already open (price_history_y2026m08, and the market_hits parent). It
-- explicitly left the RECURRENCE unfixed, and said so:
--
--     "the partition-creation path (pg_cron job 32) needs to ENABLE ROW
--      LEVEL SECURITY and attach the deny_all policy on every partition it
--      creates, or September's partition arrives open again on the 25th and
--      this migration becomes a monthly chore."
--
-- PostgreSQL does not propagate ENABLE ROW LEVEL SECURITY from a partitioned
-- parent to partitions created later, and the three
-- `ensure_next_month_*_partition()` functions only issue CREATE TABLE ...
-- PARTITION OF. So every month, on the 25th, a fresh partition appears in the
-- `public` schema with RLS off — and a table in `public` is its own PostgREST
-- resource, reachable directly at /rest/v1/<partition> regardless of the
-- parent's policies.
--
-- APPROACH
-- --------
-- A sweep rather than three rewrites. Editing the body of each
-- ensure_next_month_* function would mean transcribing three function bodies
-- correctly and would still miss any partition created by hand or by a future
-- fourth function. `secure_partition_rls()` is idempotent, runs over every
-- partition of the three partitioned parents, and fixes whatever it finds —
-- so it self-heals rather than depending on every creation path remembering.
--
-- Appended to pg_cron job 32 AFTER the three creation calls, so a
-- newly-created partition is secured in the same transaction-less run that
-- creates it.
--
-- Safe by the same argument as the migration it completes: the API connects as
-- `postgres` (rolbypassrls = true) and workers use the service role (also
-- BYPASSRLS), so enabling RLS changes nothing for any current reader or
-- writer. It only stops anon/authenticated PostgREST clients reading a
-- partition directly, which is already every sibling partition's posture.

BEGIN;

CREATE OR REPLACE FUNCTION public.secure_partition_rls()
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $fn$
DECLARE
    r          record;
    policy_nm  text;
    fixed      integer := 0;
BEGIN
    FOR r IN
        SELECT c.relname AS part_name
        FROM pg_inherits i
        JOIN pg_class c      ON c.oid = i.inhrelid
        JOIN pg_class parent ON parent.oid = i.inhparent
        JOIN pg_namespace n  ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND parent.relname IN ('market_hits', 'price_history', 'price_predictions')
          AND c.relrowsecurity = false
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.part_name);

        policy_nm := left(r.part_name || '_deny_all', 63);  -- identifier limit
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', policy_nm, r.part_name);
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR ALL USING (false) WITH CHECK (false)',
            policy_nm, r.part_name
        );

        fixed := fixed + 1;
        RAISE NOTICE 'secure_partition_rls: enabled RLS + deny_all on %', r.part_name;
    END LOOP;

    RETURN fixed;
END
$fn$;

COMMIT;

-- Wire it into the monthly partition-creation job, after the three creates.
-- cron.alter_job is used rather than unschedule/schedule so the jobid, and
-- therefore anything referencing it, is preserved.
SELECT cron.alter_job(
    job_id  => 32,
    command => $cmd$
    SELECT public.ensure_next_month_market_hits_partition();
    SELECT public.ensure_next_month_price_predictions_partition();
    SELECT public.ensure_next_month_price_history_partition();
    SELECT public.secure_partition_rls();
  $cmd$
);

-- Post-apply checks:
--   SELECT public.secure_partition_rls();          -- expect 0 (already clean)
--   SELECT command FROM cron.job WHERE jobid = 32; -- expect the 4th SELECT
--   -- expect zero rows:
--   SELECT c.relname FROM pg_inherits i
--     JOIN pg_class c ON c.oid=i.inhrelid
--     JOIN pg_class p ON p.oid=i.inhparent
--    WHERE p.relname IN ('market_hits','price_history','price_predictions')
--      AND c.relrowsecurity = false;
