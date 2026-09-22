-- 2026-09-22: the admin dashboard's tables were open to anyone with the anon key.
--
-- collectai-admin queried Supabase from the BROWSER with the anon key, behind
-- a PIN compared in the browser. To let that work, its migrations
-- (collectai-admin/supabase/migrations/003–006) gave every table an
-- `ALL … TO public USING (true)` policy, and 004b left four tables without
-- RLS at all. The anon key also ships in the mobile app, so anyone could read
-- and rewrite these tables over PostgREST.
--
-- The dashboard now reaches them only through
-- collectai-admin/src/app/api/admin/sb/[...path]/route.ts, which checks the
-- signed httpOnly admin cookie and forwards with the service-role key
-- (rolbypassrls = t). So the tables deny anon/authenticated outright: RLS on,
-- the permissive policies dropped, the grants revoked.
--
-- Checked 2026-09-22: no `.from()` in src/, app/ or supabase/functions/ names
-- any of these tables; the server reads them as `postgres` (bypasses RLS).
--
-- ⚠️ Do NOT re-run collectai-admin/supabase/migrations/00{3,4,4b,5,6}*.sql
-- against this project — they recreate the `USING (true)` policies.
--
-- FALSIFIER:
--   curl "$SUPABASE_URL/rest/v1/ugc_videos?limit=1" -H "apikey: $ANON" -> 401
--   and through the admin route, logged in -> 200 with rows.

SET lock_timeout = '5s';

DO $$
DECLARE
  t text;
  p record;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'ugc_accounts', 'ugc_content_pipeline', 'ugc_daily_snapshots',
    'ugc_pod_members', 'ugc_pods', 'ugc_swipe_file', 'ugc_tiktok_metrics',
    'ugc_video_audio', 'ugc_video_learning', 'ugc_video_scripts', 'ugc_videos',
    'content_accounts', 'content_batch_items', 'content_batches',
    'content_ideas', 'content_niches', 'content_pillars', 'content_products',
    'weekly_calendars', 'creators',
    'admin_content_config', 'admin_dev_hub', 'admin_access_log_v1',
    'subscription_events'
  ] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    FOR p IN SELECT policyname FROM pg_policies
             WHERE schemaname = 'public' AND tablename = t LOOP
      EXECUTE format('DROP POLICY %I ON public.%I', p.policyname, t);
    END LOOP;
    EXECUTE format('REVOKE ALL ON public.%I FROM anon, authenticated', t);
  END LOOP;
END $$;

RESET lock_timeout;
