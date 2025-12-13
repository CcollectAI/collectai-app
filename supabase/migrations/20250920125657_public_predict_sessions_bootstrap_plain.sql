-- Ensure required extension
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Create table if missing
CREATE TABLE IF NOT EXISTS public.predict_sessions (
  id              bigserial PRIMARY KEY,
  uuid_id         uuid DEFAULT gen_random_uuid(),
  user_id         uuid,
  item_id         bigint,
  category        text NOT NULL,
  status          text NOT NULL DEFAULT 'pending',
  confidence      numeric(5,2),
  price_low_eur   numeric(12,2),
  price_mid_eur   numeric(12,2),
  price_high_eur  numeric(12,2),
  features        jsonb,
  comps           jsonb,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

-- Ensure default on uuid_id (idempotent)
ALTER TABLE public.predict_sessions
  ALTER COLUMN uuid_id SET DEFAULT gen_random_uuid();

-- Unique index for uuid_id
CREATE UNIQUE INDEX IF NOT EXISTS predict_sessions_uuid_id_key
  ON public.predict_sessions(uuid_id);

-- updated_at trigger fn (idempotent via OR REPLACE)
CREATE OR REPLACE FUNCTION public.trg_touch_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

-- Create trigger if missing (Postgres 14+ supports IF NOT EXISTS)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'predict_sessions_touch_updated_at'
  ) THEN
    CREATE TRIGGER predict_sessions_touch_updated_at
      BEFORE UPDATE ON public.predict_sessions
      FOR EACH ROW EXECUTE FUNCTION public.trg_touch_updated_at();
  END IF;
END$$;

-- RLS: enable and set owner-only policies (safe to re-run)
ALTER TABLE public.predict_sessions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS predict_sessions_select_own ON public.predict_sessions;
DROP POLICY IF EXISTS predict_sessions_insert_own ON public.predict_sessions;
DROP POLICY IF EXISTS predict_sessions_update_own ON public.predict_sessions;

CREATE POLICY predict_sessions_select_own
  ON public.predict_sessions
  FOR SELECT TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY predict_sessions_insert_own
  ON public.predict_sessions
  FOR INSERT TO authenticated
  WITH CHECK (user_id = auth.uid());

CREATE POLICY predict_sessions_update_own
  ON public.predict_sessions
  FOR UPDATE TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());
