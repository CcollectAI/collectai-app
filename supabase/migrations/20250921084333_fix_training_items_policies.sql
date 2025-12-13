-- === Fix training_items + policies (no service_role RLS needed) ===

-- 0) Ensure nullable columns exist as intended
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='training_items' AND column_name='title') THEN
    EXECUTE 'ALTER TABLE public.training_items ALTER COLUMN title DROP NOT NULL';
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='training_items' AND column_name='image_url') THEN
    EXECUTE 'ALTER TABLE public.training_items ALTER COLUMN image_url DROP NOT NULL';
  END IF;
END$$;

-- 1) Add helpful columns if missing
ALTER TABLE public.training_items
  ADD COLUMN IF NOT EXISTS source  text,
  ADD COLUMN IF NOT EXISTS version text,
  ADD COLUMN IF NOT EXISTS idem_key text,
  ADD COLUMN IF NOT EXISTS attributes jsonb;

-- 2) Sparse unique index on idem_key (ignore if already present)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND indexname='training_items_idem_key_unique'
  ) THEN
    EXECUTE 'CREATE UNIQUE INDEX training_items_idem_key_unique
             ON public.training_items (idem_key) WHERE idem_key IS NOT NULL';
  END IF;
END$$;

-- 3) Enable RLS (safe if already enabled)
ALTER TABLE public.training_items ENABLE ROW LEVEL SECURITY;

-- 4) Policies:
--    - Allow authenticated users to SELECT everything (tighten later if needed)
--    - We do NOT need a service_role policy; service key bypasses RLS.

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

-- 5) Leave label_events.session_id type unchanged for now to avoid data loss.
--    We'll handle backfill/cast in a dedicated repair once data format is confirmed.
