-- 2026-04-24: bulk Class B — 144 public tables with RLS disabled.
-- Advisor rule: rls_disabled_in_public. Also clears 3 sensitive_columns
-- findings (overlap).
--
-- Strategy:
--   * Default: ENABLE RLS + deny-all policy. Service-role bypasses, so
--     backend workers continue to work. PostgREST anon/auth blocked.
--   * Exception list: 2 tables the frontend reads via supabase.from(...)
--     (grepped src/, app/). Those get public SELECT + owner-only writes.
--   * Skip tables that are inherited partitions (market_hits_y*) — their
--     parent market_hits has its own policy and child inherits at query
--     time via the parent. Adding deny-all on the child would break
--     direct-partition reads by service-role-equivalent backend queries.
--     Actually service-role bypasses anyway, so deny-all on child is safe.
--     Applying it for lint completeness.

DO $$
DECLARE
  t record;
  v_enabled int := 0;
  v_policies_added int := 0;
  frontend_read_exceptions text[] := ARRAY['user_public_profiles', 'twitch_creators'];
BEGIN
  FOR t IN
    SELECT c.relname,
           bool_or(col.column_name IN ('user_id', 'owner_id', 'created_by')) AS has_owner_col
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    LEFT JOIN information_schema.columns col
      ON col.table_schema = 'public' AND col.table_name = c.relname
    WHERE n.nspname = 'public'
      AND c.relkind = 'r'
      AND NOT c.relrowsecurity
    GROUP BY c.relname
  LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.relname);
    v_enabled := v_enabled + 1;

    IF t.relname = ANY(frontend_read_exceptions) THEN
      -- Public SELECT + owner-only writes
      EXECUTE format(
        'CREATE POLICY %I ON public.%I FOR SELECT USING (true)',
        t.relname || '_public_read', t.relname
      );
      -- Writes only by service-role (policy blocks anon/auth; service-role
      -- bypasses RLS regardless so it keeps working)
      EXECUTE format(
        'CREATE POLICY %I ON public.%I FOR INSERT WITH CHECK (false)',
        t.relname || '_block_writes_insert', t.relname
      );
      EXECUTE format(
        'CREATE POLICY %I ON public.%I FOR UPDATE USING (false) WITH CHECK (false)',
        t.relname || '_block_writes_update', t.relname
      );
      EXECUTE format(
        'CREATE POLICY %I ON public.%I FOR DELETE USING (false)',
        t.relname || '_block_writes_delete', t.relname
      );
      v_policies_added := v_policies_added + 4;
    ELSE
      -- Deny-all. Safe: service-role bypasses; no frontend reader.
      EXECUTE format(
        'CREATE POLICY %I ON public.%I FOR ALL USING (false) WITH CHECK (false)',
        t.relname || '_deny_all', t.relname
      );
      v_policies_added := v_policies_added + 1;
    END IF;
  END LOOP;
  RAISE NOTICE 'Enabled RLS on % tables, added % policies', v_enabled, v_policies_added;
END $$;
