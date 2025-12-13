-- Ensure table exists in public (no-op if it already exists there)
create table if not exists public.label_events (
  id bigserial primary key,
  session_id bigint not null,
  corrected_title text,
  corrected_condition text,
  corrected_price_eur numeric(12,2),
  created_at timestamptz not null default now()
);

-- Re-point (or add) FK to whichever sessions table exists.
do $$
declare
  has_public boolean := (to_regclass('public.predict_sessions') is not null);
  has_pc     boolean := (to_regclass('predictive_capture.sessions') is not null);
  con_exists boolean := exists (
    select 1 from pg_constraint
    where conname = 'label_events_session_id_fkey'
  );
begin
  -- Drop existing FK if present; we'll recreate it to the correct target.
  if con_exists then
    alter table public.label_events drop constraint label_events_session_id_fkey;
  end if;

  if has_public then
    alter table public.label_events
      add constraint label_events_session_id_fkey
      foreign key (session_id) references public.predict_sessions(id)
      on delete cascade;
  elsif has_pc then
    alter table public.label_events
      add constraint label_events_session_id_fkey
      foreign key (session_id) references predictive_capture.sessions(id)
      on delete cascade;
  else
    -- Neither target exists; leave a breadcrumb and skip FK creation.
    raise notice 'No sessions table found in public.predict_sessions or predictive_capture.sessions. FK not created.';
  end if;
end$$;

-- Ask PostgREST to reload schema (ignore if not supported)
do $$
begin
  perform pg_notify('pgrst', 'reload schema');
exception when others then
  null;
end$$;
