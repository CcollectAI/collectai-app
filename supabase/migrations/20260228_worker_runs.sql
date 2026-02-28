-- Persist worker run history to DB (survives restarts)

BEGIN;

CREATE TABLE IF NOT EXISTS public.worker_runs (
  id            bigserial   PRIMARY KEY,
  worker_name   text        NOT NULL,
  status        text        NOT NULL DEFAULT 'ok',
  started_at    timestamptz NOT NULL DEFAULT now(),
  finished_at   timestamptz NOT NULL DEFAULT now(),
  metadata      jsonb       DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_worker_runs_name_time
  ON public.worker_runs(worker_name, finished_at DESC);

-- Retention: auto-delete runs older than 30 days (if pg_cron available)
-- Otherwise, manual cleanup: DELETE FROM worker_runs WHERE finished_at < now() - interval '30 days';

-- RLS: service role only
ALTER TABLE public.worker_runs ENABLE ROW LEVEL SECURITY;
CREATE POLICY worker_runs_service_only ON public.worker_runs
  FOR ALL USING (false);

COMMIT;
