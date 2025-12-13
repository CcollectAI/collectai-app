-- Dynamic creation of v_label_events depending on where sessions live.
-- Works if sessions are at public.predict_sessions or predictive_capture.sessions.
-- If neither exists, creates a minimal view without session columns.

do $$
declare
  has_public boolean := (to_regclass('public.predict_sessions') is not null);
  has_pc     boolean := (to_regclass('predictive_capture.sessions') is not null);
  sql text;
begin
  if has_public then
    sql := $v$
      create or replace view public.v_label_events as
      select
        le.id                 as label_event_id,
        le.created_at         as label_created_at,
        le.user_id,
        le.action,
        le.corrected_title,
        le.corrected_condition,
        le.corrected_price_eur,
        le.session_id,
        le.session_uuid,
        'public'::text        as session_src,
        ps.category           as session_category,
        ps.created_at         as session_created_at
      from public.label_events le
      left join public.predict_sessions ps
        on (le.session_uuid is not null and ps.uuid_id = le.session_uuid)
        or (le.session_uuid is null and le.session_id is not null and ps.id = le.session_id);
    $v$;
  elsif has_pc then
    sql := $v$
      create or replace view public.v_label_events as
      select
        le.id                 as label_event_id,
        le.created_at         as label_created_at,
        le.user_id,
        le.action,
        le.corrected_title,
        le.corrected_condition,
        le.corrected_price_eur,
        le.session_id,
        le.session_uuid,
        'pc'::text            as session_src,
        ps.category           as session_category,
        ps.created_at         as session_created_at
      from public.label_events le
      left join predictive_capture.sessions ps
        on (le.session_uuid is not null and ps.uuid_id = le.session_uuid)
        or (le.session_uuid is null and le.session_id is not null and ps.id = le.session_id);
    $v$;
  else
    -- Fallback: project has no sessions table; make a minimal view that still works.
    sql := $v$
      create or replace view public.v_label_events as
      select
        le.id                 as label_event_id,
        le.created_at         as label_created_at,
        le.user_id,
        le.action,
        le.corrected_title,
        le.corrected_condition,
        le.corrected_price_eur,
        le.session_id,
        le.session_uuid,
        null::text            as session_src,
        null::text            as session_category,
        null::timestamptz     as session_created_at
      from public.label_events le;
    $v$;
  end if;

  execute sql;

  -- Helpful index on base table (no-op if exists)
  create index if not exists label_events_user_created_idx on public.label_events(user_id, created_at desc);

  -- Nudge PostgREST cache
  perform pg_notify('pgrst','reload schema');
end $$;
