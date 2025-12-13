-- UUID Stage C (tolerant): try to backfill and only enforce NOT NULL if clean.

do $$
declare
  has_public boolean := (to_regclass('public.predict_sessions') is not null);
  has_pc     boolean := (to_regclass('predictive_capture.sessions') is not null);
begin
  -- quick backfill from numeric FK if available
  if has_public then
    update public.label_events le
       set session_uuid = ps.uuid_id
      from public.predict_sessions ps
     where le.session_uuid is null
       and le.session_id is not null
       and ps.id = le.session_id;
  elsif has_pc then
    update public.label_events le
       set session_uuid = ps.uuid_id
      from predictive_capture.sessions ps
     where le.session_uuid is null
       and le.session_id is not null
       and ps.id = le.session_id;
  else
    raise notice 'No sessions table found; skipping quick backfill.';
  end if;
end$$;

-- helpful index (no-op if exists)
create index if not exists label_events_session_uuid_idx on public.label_events(session_uuid);

-- make numeric session_id nullable (legacy compatibility)
do $$ begin
  if exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='label_events' and column_name='session_id'
  ) then
    alter table public.label_events alter column session_id drop not null;
    comment on column public.label_events.session_id is 'LEGACY numeric linkage; prefer session_uuid';
  end if;
end $$;

-- (re)create FK on session_uuid pointing to sessions.uuid_id, whichever schema exists
do $$
declare
  has_public boolean := (to_regclass('public.predict_sessions') is not null);
  has_pc     boolean := (to_regclass('predictive_capture.sessions') is not null);
begin
  if exists (select 1 from pg_constraint where conname = 'label_events_session_uuid_fkey') then
    alter table public.label_events drop constraint label_events_session_uuid_fkey;
  end if;

  if has_public then
    alter table public.label_events
      add constraint label_events_session_uuid_fkey
      foreign key (session_uuid) references public.predict_sessions(uuid_id)
      on delete cascade;
  elsif has_pc then
    alter table public.label_events
      add constraint label_events_session_uuid_fkey
      foreign key (session_uuid) references predictive_capture.sessions(uuid_id)
      on delete cascade;
  else
    raise notice 'No sessions table found; skipping FK create';
  end if;
end $$;

-- enforce NOT NULL only if there are no remaining NULLs
do $$
declare
  remaining int;
begin
  select count(*) into remaining from public.label_events where session_uuid is null;
  if remaining = 0 then
    alter table public.label_events alter column session_uuid set not null;
    raise notice 'session_uuid enforced as NOT NULL.';
  else
    raise notice 'session_uuid still has % NULL rows — NOT enforcing in Stage-C (later backfill will handle).', remaining;
  end if;
  perform pg_notify('pgrst','reload schema');
exception when others then null;
end $$;
