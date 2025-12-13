-- 1) Sessions table (canonical)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

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

ALTER TABLE public.predict_sessions
  ALTER COLUMN uuid_id SET DEFAULT gen_random_uuid();

CREATE UNIQUE INDEX IF NOT EXISTS predict_sessions_uuid_id_key
  ON public.predict_sessions(uuid_id);

-- updated_at trigger
CREATE OR REPLACE FUNCTION public.trg_touch_updated_at()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'predict_sessions_touch_updated_at') THEN
    CREATE TRIGGER predict_sessions_touch_updated_at
    BEFORE UPDATE ON public.predict_sessions
    FOR EACH ROW EXECUTE FUNCTION public.trg_touch_updated_at();
  END IF;
END$$;

-- RLS: owner-only
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

GRANT SELECT ON public.predict_sessions TO authenticated;

-- 2) Label events (canonical UUID link)
CREATE TABLE IF NOT EXISTS public.label_events (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id uuid,
  action text NOT NULL DEFAULT 'label',
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  corrected_title text,
  corrected_condition text,
  corrected_price_eur numeric(12,2),
  session_id bigint,
  session_uuid uuid
);

-- Backfill UUID from legacy numeric id (if any)
UPDATE public.label_events le
SET session_uuid = ps.uuid_id
FROM public.predict_sessions ps
WHERE le.session_uuid IS NULL
  AND le.session_id IS NOT NULL
  AND ps.id = le.session_id;

-- Index + FK
CREATE INDEX IF NOT EXISTS idx_label_events_session_uuid ON public.label_events(session_uuid);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'label_events_session_uuid_fkey') THEN
    ALTER TABLE public.label_events
      ADD CONSTRAINT label_events_session_uuid_fkey
      FOREIGN KEY (session_uuid)
      REFERENCES public.predict_sessions (uuid_id)
      ON DELETE CASCADE;
  END IF;
END$$;

-- Only make NOT NULL when safe
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.label_events WHERE session_uuid IS NULL) THEN
    ALTER TABLE public.label_events ALTER COLUMN session_uuid SET NOT NULL;
  END IF;
END$$;

-- RLS
ALTER TABLE public.label_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS label_events_select_own ON public.label_events;
DROP POLICY IF EXISTS label_events_insert_own ON public.label_events;

CREATE POLICY label_events_select_own
  ON public.label_events
  FOR SELECT TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY label_events_insert_own
  ON public.label_events
  FOR INSERT TO authenticated
  WITH CHECK (user_id = auth.uid());

-- 3) Handy QA view
DROP VIEW IF EXISTS public.v_label_events;

CREATE VIEW public.v_label_events AS
SELECT
  le.id,
  le.user_id,
  le.session_uuid,
  ps.id   AS session_id,
  ps.category,
  ps.status AS session_status,
  le.corrected_title,
  le.corrected_condition,
  le.corrected_price_eur,
  le.created_at
FROM public.label_events le
LEFT JOIN public.predict_sessions ps
  ON ps.uuid_id = le.session_uuid;

GRANT SELECT ON public.v_label_events TO authenticated;

-- Nudge PostgREST
NOTIFY pgrst, 'reload schema';
