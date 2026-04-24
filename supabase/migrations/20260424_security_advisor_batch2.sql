-- 2026-04-24: second Supabase security-advisor batch.
-- Follow-up to 20260424_security_advisor_batch.sql. Four findings:
--   1. admin_access_log_v1  — RLS on, zero policies  (misconfig smell)
--   2. prediction_events    — no RLS, exposes session_id via PostgREST
--   3. user_category_follows — no RLS, user-scoped data public
--   4. rpc_log_notification_impression — mutable search_path
--
-- No frontend reader for any of #1-#3 (checked via grep src/). Backend
-- writers use service-role, which bypasses RLS regardless. So deny-all
-- policies are safe lockdowns that close the PostgREST surface without
-- breaking any live reader.

-- ---------------------------------------------------------------------------
-- 1. admin_access_log_v1 — explicit deny-all policy
--   RLS was already ENABLED. The advisor flags "RLS on, no policy" because
--   the default-deny is implicit and usually unintentional. Making it
--   explicit both documents intent and clears the lint.
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='public' AND tablename='admin_access_log_v1'
      AND policyname='admin_access_log_deny_all'
  ) THEN
    CREATE POLICY admin_access_log_deny_all ON public.admin_access_log_v1
      FOR ALL USING (false) WITH CHECK (false);
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 2. prediction_events — lock down PostgREST surface
--   ML telemetry (session_id + model inputs/outputs). Written by workers
--   via service-role; no frontend reader. Enable RLS + deny-all closes
--   the anon/authenticated hole without touching worker writes.
-- ---------------------------------------------------------------------------
ALTER TABLE public.prediction_events ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='public' AND tablename='prediction_events'
      AND policyname='prediction_events_deny_all'
  ) THEN
    CREATE POLICY prediction_events_deny_all ON public.prediction_events
      FOR ALL USING (false) WITH CHECK (false);
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 3. user_category_follows — enable RLS, owner-scoped CRUD
--   Schema: (user_id uuid, category_id text, created_at). User-scoped data.
--   Policy: owner can SELECT/INSERT/DELETE their own rows via anon JWT.
-- ---------------------------------------------------------------------------
ALTER TABLE public.user_category_follows ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='public' AND tablename='user_category_follows'
      AND policyname='user_category_follows_owner_select'
  ) THEN
    CREATE POLICY user_category_follows_owner_select ON public.user_category_follows
      FOR SELECT USING (auth.uid() = user_id);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='public' AND tablename='user_category_follows'
      AND policyname='user_category_follows_owner_insert'
  ) THEN
    CREATE POLICY user_category_follows_owner_insert ON public.user_category_follows
      FOR INSERT WITH CHECK (auth.uid() = user_id);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='public' AND tablename='user_category_follows'
      AND policyname='user_category_follows_owner_delete'
  ) THEN
    CREATE POLICY user_category_follows_owner_delete ON public.user_category_follows
      FOR DELETE USING (auth.uid() = user_id);
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 4. rpc_log_notification_impression — pin search_path
--   Same search_path-injection hardening as rpc_log_notification_interaction
--   in the first batch migration. Signature: (uuid, jsonb).
-- ---------------------------------------------------------------------------
ALTER FUNCTION public.rpc_log_notification_impression(
  p_notification_id uuid, p_client_context jsonb
) SET search_path = '';
