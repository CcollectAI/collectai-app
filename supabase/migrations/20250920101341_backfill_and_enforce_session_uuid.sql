-- Backfill and (conditionally) enforce NOT NULL on label_events.session_uuid.

do $$
declare
  has_public boolean := (to_regclass('public.predict_sessions') is not null);
  has_pc     boolean := (to_regclass('predictive_capture.sessions') is not null);
  remaining  integer;
begin
  if not (has_public or has_pc) then
    raise notice 'No sessions table found; skipping backfill.';
  end if;

  -- 1) Backfill from numeric FK (most reliable)
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

  -- 2) Fallback: for rows still null, try caller's latest session (by user_id)
  if has_public then
    update public.label_events le
       set session_uuid = (
         select ps.uuid_id
           from public.predict_sessions ps
          where ps.user_id = le.user_id
          order by ps.created_at desc
          limit 1
       ),
           session_id = coalesce(session_id, (
             select ps.id from public.predict_sessions ps
              where ps.user_id = le.user_id
              order by ps.created_at desc
              limit 1
           ))
     where le.session_uuid is null
       and le.user_id is not null
       and exists (select 1 from public.predict_sessions ps2 where ps2.user_id = le.user_id);
  elsif has_pc then
    update public.label_events le
       set session_uuid = (
         select ps.uuid_id
           from predictive_capture.sessions ps
          where ps.user_id = le.user_id
          order by ps.created_at desc
          limit 1
       ),
           session_id = coalesce(session_id, (
             select ps.id from predictive_capture.sessions ps
              where ps.user_id = le.user_id
              order by ps.created_at desc
              limit 1
           ))
     where le.session_uuid is null
       and le.user_id is not null
       and exists (select 1 from predictive_capture.sessions ps2 where ps2.user_id = le.user_id);
  end if;

  -- 3) Report remaining nulls, and only enforce NOT NULL if clean
  select count(*) into remaining from public.label_events where session_uuid is null;

  if remaining = 0 then
    alter table public.label_events
      alter column session_uuid set not null;
    raise notice 'session_uuid enforced as NOT NULL.';
  else
    raise notice 'session_uuid still has % NULL rows — NOT enforcing yet. Clean up and rerun.', remaining;
  end if;

  -- Helpful index (no-op if exists)
  create index if not exists label_events_session_uuid_idx on public.label_events(session_uuid);

  -- Nudge PostgREST
  perform pg_notify('pgrst','reload schema');
exception when others then
  -- Don’t hard-fail the whole push on a notification/secondary error
  raise;
end $$;
