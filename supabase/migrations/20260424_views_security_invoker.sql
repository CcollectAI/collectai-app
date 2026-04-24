-- 2026-04-24: Flip every public view to SECURITY INVOKER.
--
-- Supabase security advisor flags 225 public views as SECURITY DEFINER
-- (the Postgres default — they run with the OWNER's permissions and
-- bypass per-user RLS). For views that join user-data tables this is
-- a cross-user data leak vector through PostgREST anon-JWT calls.
--
-- security_invoker=true is the recommended fix: views enforce the
-- querying user's RLS instead of the view-creator's.
--
-- Backend impact: NONE — service-role queries bypass RLS regardless.
-- Frontend impact: queries via PostgREST anon JWT now respect RLS
-- on the underlying tables (which is what we want).
--
-- Risk: aggregate views (e.g., api_active_users_v1 counting auth.users)
-- may return empty for authenticated users if the underlying table has
-- restrictive RLS. Run server/tests/e2e/run_all.py + server/tests/e2e/
-- smoke immediately after to catch regressions.

DO $$
DECLARE
  v_name text;
  v_count int := 0;
BEGIN
  FOR v_name IN
    SELECT viewname
    FROM pg_views v
    WHERE v.schemaname = 'public'
      AND EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON c.relnamespace = n.oid
        WHERE n.nspname = v.schemaname
          AND c.relname = v.viewname
          AND (c.reloptions IS NULL
               OR NOT 'security_invoker=true' = ANY(c.reloptions))
      )
  LOOP
    EXECUTE format('ALTER VIEW public.%I SET (security_invoker = true)', v_name);
    v_count := v_count + 1;
  END LOOP;
  RAISE NOTICE 'Set security_invoker=true on % views', v_count;
END $$;
