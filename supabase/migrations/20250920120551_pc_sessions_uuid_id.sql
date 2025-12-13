-- Ensure predictive_capture.sessions exists and has uuid_id with default
do $$
begin
  if to_regclass('predictive_capture.sessions') is null then
    raise notice 'predictive_capture.sessions not found; skipping uuid patch';
    return;
  end if;

  -- pgcrypto extension for gen_random_uuid (if not already present)
  create extension if not exists pgcrypto;

  -- Add uuid_id if missing
  if not exists (
    select 1 from information_schema.columns
    where table_schema='predictive_capture' and table_name='sessions' and column_name='uuid_id'
  ) then
    alter table predictive_capture.sessions
      add column uuid_id uuid default gen_random_uuid();
  end if;

  -- Make not null (only if all rows populated)
  begin
    update predictive_capture.sessions set uuid_id = gen_random_uuid() where uuid_id is null;
    alter table predictive_capture.sessions alter column uuid_id set not null;
  exception when others then
    raise notice 'Could not enforce NOT NULL on predictive_capture.sessions.uuid_id (will remain nullable)';
  end;

  -- Uniqueness
  create unique index if not exists predictive_sessions_uuid_id_key on predictive_capture.sessions(uuid_id);

  -- Nudge PostgREST (no-op if not installed)
  perform pg_notify('pgrst','reload schema');
end $$;
