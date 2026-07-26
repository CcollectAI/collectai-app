-- NOT APPLIED. Written 2026-07-27, deliberately left unapplied — see below.
--
-- Apply via: psql $DB_DSN_DIRECT -f 20260727_rls_disabled_partitions.sql
-- After applying, re-run the three preflight gates (schema_drift_check,
-- preflight_rls_check, preflight_schema_lock). Enabling RLS touches neither
-- columns nor constraints, so schema.lock.json should not move — confirm, do
-- not assume.
--
-- WHY THIS EXISTS
-- ---------------
-- These are the first two findings of the rewritten
-- server/scripts/audit_rls_coverage.py. They were invisible to the previous
-- version, which only scanned ordinary tables (relkind='r') carrying a
-- `user_id` column:
--
--   price_history_y2026m08   RLS off, 0 policies.  In scope: FK -> items,
--                            and items.user_id is what makes a price-history
--                            row attributable to a person.
--   market_hits              RLS off, 0 policies.  The partitioned PARENT.
--                            Every one of its partitions (market_hits_default,
--                            _archive, _y2026m07/08/09) has RLS enabled with a
--                            deny_all policy; the parent has neither.
--
-- Root cause, and the reason this will recur: PostgreSQL does NOT propagate
-- ENABLE ROW LEVEL SECURITY from a partitioned parent to partitions created
-- later, and does not infer it on the parent from its children. pg_cron job 32
-- creates next month's partition on the 25th of each month. price_history_y2026m08
-- was created on 2026-07-25 and came up with RLS off, while _y2026m07 and
-- _default both have it on. So this is not a one-off: every monthly partition
-- ships this way unless the partition-creation function is changed too.
--
-- Severity today is low and dated. price_history_y2026m08 holds 0 rows because
-- August has not started; from 2026-08-01 it becomes the live partition. A
-- table in the `public` schema is its own PostgREST resource, so a client can
-- request the partition directly (/rest/v1/price_history_y2026m08) and bypass
-- the parent's policies entirely. Reads through the parent are correctly gated
-- — price_history the parent has RLS on with 2 policies — which is exactly why
-- this went unnoticed.
--
-- WHY IT IS NOT APPLIED
-- ---------------------
-- The task that produced these findings was scoped code-only. This is DDL on
-- prod, so it is written and left for an explicit decision. It is safe to apply
-- as-is: the API connects as `postgres` (rolbypassrls = true, verified) and
-- workers use the service role (also BYPASSRLS), so enabling RLS changes
-- nothing for any current reader or writer — it only stops anonymous and
-- authenticated PostgREST clients from reading the tables directly, which is
-- already the posture of every sibling partition.

BEGIN;

-- The August price_history partition, created by pg_cron without RLS.
ALTER TABLE public.price_history_y2026m08 ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS price_history_y2026m08_deny_all ON public.price_history_y2026m08;
CREATE POLICY price_history_y2026m08_deny_all ON public.price_history_y2026m08
    FOR ALL USING (false) WITH CHECK (false);

-- The market_hits parent. Its partitions are all deny-all already; the parent
-- being open makes them reachable through it.
ALTER TABLE public.market_hits ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS market_hits_deny_all ON public.market_hits;
CREATE POLICY market_hits_deny_all ON public.market_hits
    FOR ALL USING (false) WITH CHECK (false);

COMMIT;

-- FOLLOW-UP, not fixed here: the partition-creation path (pg_cron job 32) needs
-- to ENABLE ROW LEVEL SECURITY and attach the deny_all policy on every
-- partition it creates, or September's partition arrives open again on the 25th
-- and this migration becomes a monthly chore. audit_rls_coverage.py will now
-- catch it either way, which is the point — but a gate that fires every month
-- for the same reason is a bug report, not a fix.
