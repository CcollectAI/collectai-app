-- 1) Make sure column exists
ALTER TABLE public.training_items
  ADD COLUMN IF NOT EXISTS session_uuid uuid;

-- 2) If session_uuid is currently NOT uuid, try to convert safely when all values are NULL or UUID-ish
DO $$
DECLARE
  coltype text;
  badcnt  bigint;
BEGIN
  SELECT data_type INTO coltype
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name='training_items' AND column_name='session_uuid';

  IF coltype <> 'uuid' THEN
    SELECT count(*) INTO badcnt
    FROM public.training_items
    WHERE session_uuid IS NOT NULL
      AND session_uuid::text !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';

    IF badcnt = 0 THEN
      ALTER TABLE public.training_items
        ALTER COLUMN session_uuid TYPE uuid
        USING (NULLIF(session_uuid::text, '')::uuid);
    ELSE
      RAISE NOTICE 'Skipped TYPE change: found % non-uuid values in session_uuid', badcnt;
    END IF;
  END IF;
END$$;

-- 3) Unique index to support upsert on session_uuid
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND tablename='training_items' AND indexname='training_items_session_uuid_key'
  ) THEN
    CREATE UNIQUE INDEX training_items_session_uuid_key ON public.training_items(session_uuid);
  END IF;
END$$;

-- 4) Owner-only RLS (idempotent)
ALTER TABLE public.training_items ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='training_items' AND policyname='training_items_select_own') THEN
    CREATE POLICY training_items_select_own
      ON public.training_items FOR SELECT TO authenticated
      USING (user_id = auth.uid());
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='training_items' AND policyname='training_items_insert_own') THEN
    CREATE POLICY training_items_insert_own
      ON public.training_items FOR INSERT TO authenticated
      WITH CHECK (user_id = auth.uid());
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='training_items' AND policyname='training_items_update_own') THEN
    CREATE POLICY training_items_update_own
      ON public.training_items FOR UPDATE TO authenticated
      USING (user_id = auth.uid())
      WITH CHECK (user_id = auth.uid());
  END IF;
END$$;

-- 5) Touch PostgREST
NOTIFY pgrst, 'reload schema';
