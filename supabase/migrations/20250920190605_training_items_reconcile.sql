-- Ensure the table exists (do nothing if it already does)
CREATE TABLE IF NOT EXISTS public.training_items (
  id                  bigserial PRIMARY KEY
);

-- === Add any missing columns (all idempotent) ===
ALTER TABLE public.training_items
  ADD COLUMN IF NOT EXISTS session_uuid         uuid,
  ADD COLUMN IF NOT EXISTS user_id              uuid,
  ADD COLUMN IF NOT EXISTS category             text,
  ADD COLUMN IF NOT EXISTS raw_title            text,
  ADD COLUMN IF NOT EXISTS raw_condition        text,
  ADD COLUMN IF NOT EXISTS raw_price_eur        numeric(12,2),
  ADD COLUMN IF NOT EXISTS corrected_title      text,
  ADD COLUMN IF NOT EXISTS corrected_condition  text,
  ADD COLUMN IF NOT EXISTS corrected_price_eur  numeric(12,2),
  ADD COLUMN IF NOT EXISTS created_at           timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at           timestamptz NOT NULL DEFAULT now();

-- If you previously had a numeric training_items.session_id, backfill session_uuid
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='training_items' AND column_name='session_id'
  ) THEN
    -- backfill from predict_sessions.id → uuid_id
    IF to_regclass('public.predict_sessions') IS NOT NULL THEN
      EXECUTE $q$
        UPDATE public.training_items ti
        SET session_uuid = ps.uuid_id
        FROM public.predict_sessions ps
        WHERE ti.session_uuid IS NULL
          AND ti.session_id IS NOT NULL
          AND ps.id = ti.session_id
      $q$;
    END IF;
  END IF;
END$$;

-- Also try to backfill from label_events (if training rows link to labels via, e.g., label_event_id)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='training_items' AND column_name='label_event_id'
  ) THEN
    IF to_regclass('public.label_events') IS NOT NULL THEN
      EXECUTE $q$
        UPDATE public.training_items ti
        SET session_uuid = le.session_uuid
        FROM public.label_events le
        WHERE ti.session_uuid IS NULL
          AND ti.label_event_id = le.id
      $q$;
    END IF;
  END IF;
END$$;

-- Index (safe if it already exists)
CREATE INDEX IF NOT EXISTS idx_training_items_session_uuid ON public.training_items(session_uuid);
CREATE INDEX IF NOT EXISTS idx_training_items_user        ON public.training_items(user_id);
CREATE INDEX IF NOT EXISTS idx_training_items_category    ON public.training_items(category);

-- FK to sessions by UUID (safe if exists)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='training_items_session_uuid_fkey') THEN
    IF to_regclass('public.predict_sessions') IS NOT NULL THEN
      ALTER TABLE public.training_items
        ADD CONSTRAINT training_items_session_uuid_fkey
        FOREIGN KEY (session_uuid)
        REFERENCES public.predict_sessions (uuid_id)
        ON DELETE CASCADE;
    END IF;
  END IF;
END$$;

-- updated_at trigger (shared function may already exist)
CREATE OR REPLACE FUNCTION public.trg_touch_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='training_items_touch_updated_at') THEN
    CREATE TRIGGER training_items_touch_updated_at
      BEFORE UPDATE ON public.training_items
      FOR EACH ROW EXECUTE FUNCTION public.trg_touch_updated_at();
  END IF;
END$$;

-- RLS: owner-only (non-destructive)
ALTER TABLE public.training_items ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='training_items' AND policyname='training_items_select_own') THEN
    -- ok
  ELSE
    CREATE POLICY training_items_select_own
      ON public.training_items
      FOR SELECT TO authenticated
      USING (user_id = auth.uid());
  END IF;

  IF EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='training_items' AND policyname='training_items_insert_own') THEN
  ELSE
    CREATE POLICY training_items_insert_own
      ON public.training_items
      FOR INSERT TO authenticated
      WITH CHECK (user_id = auth.uid());
  END IF;

  IF EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='training_items' AND policyname='training_items_update_own') THEN
  ELSE
    CREATE POLICY training_items_update_own
      ON public.training_items
      FOR UPDATE TO authenticated
      USING (user_id = auth.uid())
      WITH CHECK (user_id = auth.uid());
  END IF;
END$$;

-- Only enforce NOT NULL when data is healthy (optional)
-- DO $$
-- BEGIN
--   IF NOT EXISTS (SELECT 1 FROM public.training_items WHERE session_uuid IS NULL) THEN
--     ALTER TABLE public.training_items ALTER COLUMN session_uuid SET NOT NULL;
--   END IF;
-- END$$;

-- Recreate metrics view (non-breaking)
CREATE OR REPLACE VIEW public.v_predict_metrics AS
SELECT
  ti.user_id,
  ti.category,
  count(*) AS n_samples,
  avg( (ti.raw_price_eur - ti.corrected_price_eur)::numeric )                            AS price_bias,
  avg( abs(ti.raw_price_eur - ti.corrected_price_eur)::numeric )                         AS price_mae,
  sqrt(avg( (ti.raw_price_eur - ti.corrected_price_eur)^2 ))                              AS price_rmse,
  (sum( CASE WHEN ti.raw_condition IS NOT NULL AND ti.corrected_condition IS NOT NULL AND ti.raw_condition = ti.corrected_condition THEN 1 ELSE 0 END )::numeric
     / NULLIF(sum( CASE WHEN ti.raw_condition IS NOT NULL AND ti.corrected_condition IS NOT NULL THEN 1 ELSE 0 END ),0)) AS condition_accuracy
FROM public.training_items ti
GROUP BY ti.user_id, ti.category;

GRANT SELECT ON public.v_predict_metrics TO authenticated;

-- Refresh PostgREST
NOTIFY pgrst, 'reload schema';
