-- 2026-09-22: two more admin tables that anyone could write, missed by 20260922c.
--
-- calendar_items and generated_captions carry `ALL … TO public USING (true)`
-- (collectai-admin/supabase/migrations/006_content_machine.sql), and anon held
-- INSERT/UPDATE/DELETE. 20260922c chose its 24 tables by NAME PATTERN
-- (ugc_*, content_*, admin_*), and these two match none of them. They were
-- found by the watchdog's new "permissive write policy" check on its first
-- calibration run, which enumerates the policies themselves instead.
--
-- Nothing reads or writes them: no reference in src/, app/,
-- supabase/functions/, collectai-admin/src/ or server/, and 0 rows in both
-- (2026-09-22). So they are locked, not moved behind the admin proxy.
--
-- FALSIFIER: the watchdog check "Write policy open to every client role"
-- reports nothing; `curl "$SUPABASE_URL/rest/v1/calendar_items?limit=1"
-- -H "apikey: $ANON"` -> 401.

DO $$
DECLARE
  t text;
  p record;
BEGIN
  FOREACH t IN ARRAY ARRAY['calendar_items', 'generated_captions'] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    FOR p IN SELECT policyname FROM pg_policies
             WHERE schemaname = 'public' AND tablename = t LOOP
      EXECUTE format('DROP POLICY %I ON public.%I', p.policyname, t);
    END LOOP;
    EXECUTE format('REVOKE ALL ON public.%I FROM anon, authenticated', t);
  END LOOP;
END $$;
