-- 2026-04-24: two Supabase security-advisor findings.

-- ---------------------------------------------------------------------------
-- 1. price_cache: enable RLS
--   Hash-keyed FX/price cache. Server workers (service-role) write; mobile
--   clients (anon JWT) read by keyhash. Service-role bypasses RLS for the
--   writer path; explicit SELECT policy covers the reader path. Direct
--   INSERT from anon is blocked.
-- ---------------------------------------------------------------------------
ALTER TABLE public.price_cache ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='price_cache' AND policyname='price_cache_public_read') THEN
    CREATE POLICY price_cache_public_read ON public.price_cache
      FOR SELECT USING (true);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='price_cache' AND policyname='price_cache_no_direct_write') THEN
    CREATE POLICY price_cache_no_direct_write ON public.price_cache
      FOR INSERT WITH CHECK (false);
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 2. rpc_log_notification_interaction: pin search_path
--   Functions without explicit search_path are exploitable if anyone
--   creates a colliding object in a writable schema (search_path-injection).
--   Setting empty search_path forces fully-qualified references inside the
--   function body and makes hijack via shadow-objects impossible.
-- ---------------------------------------------------------------------------
ALTER FUNCTION public.rpc_log_notification_interaction(
  p_notification_id uuid, p_kind text, p_meta jsonb
) SET search_path = '';
