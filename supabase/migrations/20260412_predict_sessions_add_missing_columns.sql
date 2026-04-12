-- Add columns required by predict-sessions edge function
-- (source, version, idem_key, meta were referenced but never added to the table)

ALTER TABLE public.predict_sessions
  ADD COLUMN IF NOT EXISTS source   text,
  ADD COLUMN IF NOT EXISTS version  text,
  ADD COLUMN IF NOT EXISTS idem_key text,
  ADD COLUMN IF NOT EXISTS meta     jsonb DEFAULT '{}'::jsonb;

-- Sparse unique index on idem_key for idempotent session creation
CREATE UNIQUE INDEX IF NOT EXISTS predict_sessions_idem_key_unique
  ON public.predict_sessions (idem_key) WHERE idem_key IS NOT NULL;

-- Default user_id from JWT so edge functions don't need to set it explicitly
ALTER TABLE public.predict_sessions
  ALTER COLUMN user_id SET DEFAULT auth.uid();

-- Relax insert policy: allow user_id = auth.uid() OR NULL (auto-filled by default)
DROP POLICY IF EXISTS predict_sessions_insert_own ON public.predict_sessions;
CREATE POLICY predict_sessions_insert_own
  ON public.predict_sessions
  FOR INSERT TO authenticated
  WITH CHECK (user_id = auth.uid() OR user_id IS NULL);

-- Nudge PostgREST to pick up new columns
NOTIFY pgrst, 'reload schema';
