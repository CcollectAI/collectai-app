-- 0) Backfill user_id on existing rows from sessions (public.predict_sessions or predictive_capture.sessions)
do $$
declare
  has_public boolean := (to_regclass('public.predict_sessions') is not null);
  has_pc     boolean := (to_regclass('predictive_capture.sessions') is not null);
begin
  if has_public then
    update public.label_events le
       set user_id = ps.user_id
      from public.predict_sessions ps
     where le.user_id is null
       and le.session_id is not null
       and ps.id = le.session_id;
  elsif has_pc then
    update public.label_events le
       set user_id = ps.user_id
      from predictive_capture.sessions ps
     where le.user_id is null
       and le.session_id is not null
       and ps.id = le.session_id;
  else
    raise notice 'No sessions table found; skipping backfill.';
  end if;
end$$;

-- 1) Ensure helper trigger fills session_uuid (from Stage A) AND user_id from session owner
create or replace function public.trg_label_events_fill()
returns trigger
language plpgsql
as $$
declare
  v_uuid uuid;
  v_user uuid;
begin
  -- session_uuid from numeric session_id if needed
  if NEW.session_uuid is null and NEW.session_id is not null then
    if to_regclass('public.predict_sessions') is not null then
      select uuid_id, user_id into v_uuid, v_user from public.predict_sessions where id = NEW.session_id;
    elsif to_regclass('predictive_capture.sessions') is not null then
      select uuid_id, user_id into v_uuid, v_user from predictive_capture.sessions where id = NEW.session_id;
    end if;
    if NEW.session_uuid is null then NEW.session_uuid := v_uuid; end if;
    if NEW.user_id is null then NEW.user_id := v_user; end if;
  end if;

  return NEW;
end
$$;

do $$
begin
  if exists (select 1 from pg_trigger where tgname = 'trg_label_events_fill_bi') then
    drop trigger trg_label_events_fill_bi on public.label_events;
  end if;

  create trigger trg_label_events_fill_bi
    before insert on public.label_events
    for each row execute function public.trg_label_events_fill();
end$$;

-- 2) Nudge PostgREST cache
do $$ begin perform pg_notify('pgrst','reload schema'); exception when others then null; end $$;
