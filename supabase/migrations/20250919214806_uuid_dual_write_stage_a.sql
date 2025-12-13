-- Stage A: Add UUIDs alongside numeric IDs + keep them in sync

-- 0) Ensure pgcrypto for gen_random_uuid()
create extension if not exists pgcrypto;

-- 1) Add uuid_id to sessions table(s) if present
do $$
declare
  has_public boolean := (to_regclass('public.predict_sessions') is not null);
  has_pc     boolean := (to_regclass('predictive_capture.sessions') is not null);
begin
  if not (has_public or has_pc) then
    raise notice 'No sessions table found; skipping uuid_dual_write_stage_a (non-fatal).';
    return;
  end if;

  if has_public then
    alter table public.predict_sessions
      add column if not exists uuid_id uuid default gen_random_uuid();
    alter table public.predict_sessions
      alter column uuid_id set not null;
    create unique index if not exists predict_sessions_uuid_id_key on public.predict_sessions(uuid_id);
  end if;

  if has_pc then
    alter table predictive_capture.sessions
      add column if not exists uuid_id uuid default gen_random_uuid();
    alter table predictive_capture.sessions
      alter column uuid_id set not null;
    create unique index if not exists predictive_sessions_uuid_id_key on predictive_capture.sessions(uuid_id);
  end if;
end$$;

-- 2) Add session_uuid to label_events (nullable for now)
alter table public.label_events
  add column if not exists session_uuid uuid;

-- 3) Backfill session_uuid where possible
do $$
declare
  has_public boolean := (to_regclass('public.predict_sessions') is not null);
  has_pc     boolean := (to_regclass('predictive_capture.sessions') is not null);
begin
  if has_public then
    update public.label_events le
       set session_uuid = ps.uuid_id
      from public.predict_sessions ps
     where le.session_id is not null
       and le.session_uuid is null
       and ps.id = le.session_id;
  elsif has_pc then
    update public.label_events le
       set session_uuid = ps.uuid_id
      from predictive_capture.sessions ps
     where le.session_id is not null
       and le.session_uuid is null
       and ps.id = le.session_id;
  end if;
end$$;

-- 4) Function + trigger: set session_uuid automatically on insert
create or replace function public.trg_label_events_set_uuid()
returns trigger
language plpgsql
as $body$
declare
  v_uuid uuid;
begin
  -- Respect any explicit session_uuid provided
  if NEW.session_uuid is not null then
    return NEW;
  end if;

  if NEW.session_id is not null then
    if to_regclass('public.predict_sessions') is not null then
      select uuid_id into v_uuid from public.predict_sessions where id = NEW.session_id;
    elsif to_regclass('predictive_capture.sessions') is not null then
      select uuid_id into v_uuid from predictive_capture.sessions where id = NEW.session_id;
    end if;
  end if;

  NEW.session_uuid := coalesce(NEW.session_uuid, v_uuid);
  return NEW;
end
$body$;

do $$
begin
  if exists (select 1 from pg_trigger where tgname = 'trg_label_events_set_uuid_bi') then
    drop trigger trg_label_events_set_uuid_bi on public.label_events;
  end if;

  create trigger trg_label_events_set_uuid_bi
    before insert on public.label_events
    for each row execute function public.trg_label_events_set_uuid();
end$$;

-- 5) Nudge PostgREST to reload schema (best effort)
do $$ begin
  perform pg_notify('pgrst','reload schema');
exception when others then null; end $$;
