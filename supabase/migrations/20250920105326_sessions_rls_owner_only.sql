do $$
declare
  has_public boolean := (to_regclass('public.predict_sessions') is not null);
  has_pc     boolean := (to_regclass('predictive_capture.sessions') is not null);
begin
  if has_public then
    alter table public.predict_sessions enable row level security;

    -- Drop any old permissive policies (ignore errors)
    begin
      drop policy if exists predict_sessions_select_auth on public.predict_sessions;
      drop policy if exists predict_sessions_all on public.predict_sessions;
    exception when others then null; end;

    create policy predict_sessions_select_own
      on public.predict_sessions
      for select
      to authenticated
      using (user_id = auth.uid());

  elsif has_pc then
    alter table predictive_capture.sessions enable row level security;

    begin
      drop policy if exists sessions_select_auth on predictive_capture.sessions;
      drop policy if exists sessions_all on predictive_capture.sessions;
    exception when others then null; end;

    create policy sessions_select_own
      on predictive_capture.sessions
      for select
      to authenticated
      using (user_id = auth.uid());

  else
    raise notice 'No sessions table found; skipping sessions RLS.';
  end if;

  perform pg_notify('pgrst','reload schema');
end $$;
