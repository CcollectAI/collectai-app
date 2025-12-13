-- === training_items dual-write patch ===
-- Safe guards: IF EXISTS / IF NOT EXISTS and NULLability relax

-- 1) Make columns nullable to avoid strict failures
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'training_items' AND column_name = 'title'
  ) THEN
    EXECUTE 'ALTER TABLE public.training_items ALTER COLUMN title DROP NOT NULL';
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'training_items' AND column_name = 'image_url'
  ) THEN
    EXECUTE 'ALTER TABLE public.training_items ALTER COLUMN image_url DROP NOT NULL';
  END IF;
END$$;

-- 2) Add provenance fields if missing
ALTER TABLE public.training_items
  ADD COLUMN IF NOT EXISTS source text,
  ADD COLUMN IF NOT EXISTS version text,
  ADD COLUMN IF NOT EXISTS idem_key text;

-- 3) Add a stable, sparse uniqueness on idem_key to dedupe dual-writes
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='training_items_idem_key_unique'
  ) THEN
    EXECUTE 'CREATE UNIQUE INDEX training_items_idem_key_unique ON public.training_items (idem_key) WHERE idem_key IS NOT NULL';
  END IF;
END$$;

-- 4) Align label_events.session_id to uuid if mismatched (safe cast when possible)
DO $$
DECLARE
  col_type text;
BEGIN
  SELECT data_type INTO col_type
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name='label_events' AND column_name='session_id';

  IF col_type IS NOT NULL AND col_type <> 'uuid' THEN
    -- Attempt cast using uuid() semantics; adapt if your session ids are text uuids
    BEGIN
      EXECUTE 'ALTER TABLE public.label_events ALTER COLUMN session_id TYPE uuid USING session_id::uuid';
    EXCEPTION WHEN others THEN
      RAISE NOTICE 'Could not cast label_events.session_id to uuid; please check data.';
    END;
  END IF;
END$$;

-- 5) Storage bucket policies stub (run on initial setup)
--   If you use a bucket named 'predictive', create policies here.
--   NOTE: Edge Functions use service role; users need RESTRICTED reads.
--   Uncomment if needed.

-- DO $$
-- BEGIN
--   IF NOT EXISTS (SELECT 1 FROM storage.buckets WHERE name='predictive') THEN
--     PERFORM storage.create_bucket('predictive', public := false);
--   END IF;
-- END$$;

-- RLS policies for storage.objects (predictive)
-- REVOKE ALL ON storage.objects FROM anon, authenticated; -- optional tighten
-- CREATE POLICY IF NOT EXISTS "service can write predictive"
--   ON storage.objects FOR INSERT TO service_role USING (bucket_id = 'predictive') WITH CHECK (bucket_id = 'predictive');
-- CREATE POLICY IF NOT EXISTS "auth can read own predictive"
--   ON storage.objects FOR SELECT TO authenticated USING (bucket_id = 'predictive');

-- 6) RLS on training_items: allow service_role full, auth read (adjust as you prefer)
ALTER TABLE public.training_items ENABLE ROW LEVEL SECURITY;


-- Safe policy for authenticated SELECT on training_items (outside of DO $$ to avoid nesting issues)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='public' AND tablename='training_items'
      AND policyname='auth_select_training_items'
  ) THEN
    EXECUTE 'CREATE POLICY "auth_select_training_items"
             ON public.training_items
             FOR SELECT
             TO authenticated
             USING (true)';
  END IF;
END$$;
