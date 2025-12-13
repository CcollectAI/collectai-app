-- suggestion_logs: ensure table/cols/index
create table if not exists public.suggestion_logs (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  category text,
  model_version text,
  request_id text,
  features jsonb,
  price numeric,
  context jsonb
);
do $$
begin
  if not exists (select 1 from information_schema.columns where table_schema='public' and table_name='suggestion_logs' and column_name='context') then
    alter table public.suggestion_logs add column context jsonb;
  end if;
  if not exists (select 1 from pg_indexes where schemaname='public' and indexname='suggestion_logs_request_id_key') then
    create unique index suggestion_logs_request_id_key on public.suggestion_logs (request_id) where request_id is not null;
  end if;
end$$;

-- model_training_runs: ensure table + started_at default
create table if not exists public.model_training_runs (
  id uuid primary key default gen_random_uuid(),
  category text not null,
  version text not null,
  dataset_uri text,
  artifact_etag text,
  artifact_uri text,
  status text not null default 'started',
  error text,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  params jsonb,
  metrics jsonb
);
do $$
begin
  if exists (select 1 from information_schema.columns where table_schema='public' and table_name='model_training_runs' and column_name='started_at') then
    execute 'alter table public.model_training_runs alter column started_at set default now()';
  end if;
end$$;

-- helper index
create index if not exists mtr_cat_ver on public.model_training_runs (category, version);

-- refresh PostgREST cache (Supabase)
notify pgrst, 'reload schema';
