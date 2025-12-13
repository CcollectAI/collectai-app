-- Ensure table
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

-- Backfill session_uuid from session_id, if any legacy rows
UPDATE public.label_events le
SET session_uuid = ps.uuid_id
FROM public.predict_sessions ps
WHERE le.session_uuid IS NULL
  AND le.session_id IS NOT NULL
  AND ps.id = le.session_id;

-- Index + FK (idempotent)
CREATE INDEX IF NOT EXISTS idx_label_events_session_uuid ON public.label_events(session_uuid);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'label_events_session_uuid_fkey'
  ) THEN
    ALTER TABLE public.label_events
      ADD CONSTRAINT label_events_session_uuid_fkey
      FOREIGN KEY (session_uuid)
      REFERENCES public.predict_sessions (uuid_id)
      ON DELETE CASCADE;
  END IF;
END$$;

-- Make session_uuid required only if no NULLs remain
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.label_events WHERE session_uuid IS NULL) THEN
    ALTER TABLE public.label_events ALTER COLUMN session_uuid SET NOT NULL;
  END IF;
END$$;

-- RLS hardening
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

NOTIFY pgrst, 'reload schema';
