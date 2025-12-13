create table if not exists public.model_registry (
  id bigserial primary key,
  name text not null,            -- e.g., "price-v1"
  version text not null,         -- e.g., "2025-09-21"
  uri text,                      -- s3://... or https://lambda-url
  created_at timestamptz not null default now(),
  unique(name, version)
);

create table if not exists public.prediction_events (
  id bigserial primary key,
  session_id uuid,
  model_name text not null,
  model_version text not null,
  input jsonb not null,
  output jsonb not null,
  latency_ms integer,
  created_at timestamptz not null default now()
);

create table if not exists public.eval_results (
  id bigserial primary key,
  model_name text not null,
  model_version text not null,
  metric text not null,          -- e.g., "MAE"
  value numeric not null,
  sample_size integer not null,
  created_at timestamptz not null default now()
);
