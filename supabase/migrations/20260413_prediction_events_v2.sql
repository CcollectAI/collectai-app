-- prediction_events_v2: used by log-prediction and log-actual edge functions
CREATE TABLE IF NOT EXISTS public.prediction_events_v2 (
  id                bigserial PRIMARY KEY,
  created_at        timestamptz NOT NULL DEFAULT now(),
  model_name        text,
  model_version     text,
  model_id          uuid,
  artifact_uri      text,
  category          text,
  title             text,
  platform          text,
  item_id           text,
  features          jsonb,
  input             jsonb,
  output            jsonb,
  prediction        numeric,
  reason            text,
  gated             boolean DEFAULT false,
  actual_eur        numeric,
  user_id           uuid,
  canonical_key     text,
  checklist_item_id uuid,
  q10_eur           numeric,
  q50_eur           numeric,
  q90_eur           numeric,
  confidence_score  numeric,
  comps_count       integer,
  trace             jsonb
);

NOTIFY pgrst, 'reload schema';
