-- 2026-04-24: second security-advisor sweep. Cleanups for regressions
-- introduced by today's partition migrations + view repointing.
--
-- Regressions observed after today's schema work:
--   * 15 new SECURITY DEFINER views — CREATE OR REPLACE defaults to DEFINER,
--     wiping out the earlier security_invoker=true flip.
--   * 15 partition children (price_predictions_y*, price_history_y*, *_default)
--     had no RLS. Partition inheritance enforces parent RLS at query time
--     via parent, but direct access to a child bypasses it. Uniform fix:
--     enable RLS + deny-all on each child (service-role still bypasses).
--   * 6 tables (admin_content_config, admin_dev_hub, image_embeddings,
--     item_embeddings, model_registry, model_runs) had their only policy
--     dropped earlier as "overbroad" — now RLS is on but no policy. Add
--     explicit deny-all.
--   * 10 materialized views exposed via PostgREST — REVOKE from anon/auth.

-- ---------------------------------------------------------------------------
-- 1. Re-flip all public views to SECURITY INVOKER
-- ---------------------------------------------------------------------------
DO $$
DECLARE v_name text; v_count int := 0;
BEGIN
  FOR v_name IN
    SELECT viewname FROM pg_views v
    WHERE v.schemaname = 'public'
      AND EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON c.relnamespace = n.oid
        WHERE n.nspname = v.schemaname AND c.relname = v.viewname
          AND (c.reloptions IS NULL
               OR NOT 'security_invoker=true' = ANY(c.reloptions))
      )
  LOOP
    EXECUTE format('ALTER VIEW public.%I SET (security_invoker = true)', v_name);
    v_count := v_count + 1;
  END LOOP;
  RAISE NOTICE 'Flipped % views to security_invoker=true', v_count;
END $$;

-- ---------------------------------------------------------------------------
-- 2. Enable RLS + deny-all on all partition children (and any other
--    public tables with no RLS — catches future regressions).
-- ---------------------------------------------------------------------------
DO $$
DECLARE t record; v_count int := 0;
BEGIN
  FOR t IN
    SELECT c.relname
    FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relkind='r' AND NOT c.relrowsecurity
  LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.relname);
    EXECUTE format(
      'CREATE POLICY %I ON public.%I FOR ALL USING (false) WITH CHECK (false)',
      t.relname || '_deny_all', t.relname
    );
    v_count := v_count + 1;
  END LOOP;
  RAISE NOTICE 'Enabled RLS + deny-all on % tables', v_count;
END $$;

-- ---------------------------------------------------------------------------
-- 3. Deny-all on the 6 tables whose overbroad policies we dropped earlier
-- ---------------------------------------------------------------------------
DO $$
DECLARE t record; v_count int := 0;
BEGIN
  FOR t IN
    SELECT c.relname
    FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relkind='r' AND c.relrowsecurity
      AND NOT EXISTS (SELECT 1 FROM pg_policies p
                      WHERE p.schemaname='public' AND p.tablename=c.relname)
  LOOP
    EXECUTE format(
      'CREATE POLICY %I ON public.%I FOR ALL USING (false) WITH CHECK (false)',
      t.relname || '_deny_all', t.relname
    );
    v_count := v_count + 1;
  END LOOP;
  RAISE NOTICE 'Added deny-all on % RLS-on-no-policy tables', v_count;
END $$;

-- ---------------------------------------------------------------------------
-- 4. REVOKE PostgREST-facing grants on 10 materialized views.
--    Service-role keeps access (it's granted separately as the owner).
-- ---------------------------------------------------------------------------
DO $$
DECLARE m record; v_count int := 0;
BEGIN
  FOR m IN
    SELECT matviewname FROM pg_matviews WHERE schemaname='public'
  LOOP
    EXECUTE format('REVOKE ALL ON public.%I FROM anon, authenticated', m.matviewname);
    v_count := v_count + 1;
  END LOOP;
  RAISE NOTICE 'Revoked anon/auth on % materialized views', v_count;
END $$;
