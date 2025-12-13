-- Stage B: enforce UUID linkage while numeric stays for compatibility

-- 0) Detect sessions table location
do $$
declare
  has_public boolean := (to_regclass('public.predict_sessions') is not null);
  has_pc     boolean := (to_regclass('predictive_capture.sessions') is not null);
begin
  if not (has_public or has_pc) then
    raise notice 'No sessions table found; skipping Stage B (non-fatal).';
    return;
  end if;

  -- 1) Backfill any remaining null session_uuid (defensive)
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
  end if;

  -- 2) Make session_uuid required
  alter table public.label_events
    alter column session_uuid set not null;

  -- 3) Recreate FK to uuid target (drop old if exists)
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
  end if;

end$$;

-- 4) Helpful indexes
create index if not exists label_events_session_uuid_idx on public.label_events(session_uuid);
create index if not exists label_events_created_at_idx on public.label_events(created_at);

-- 5) Nudge PostgREST
do $$ begin perform pg_notify('pgrst','reload schema'); exception when others then null; end $$;
