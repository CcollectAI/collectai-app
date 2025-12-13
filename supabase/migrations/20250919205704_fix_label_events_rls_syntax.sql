-- Ensure RLS is on
alter table public.label_events enable row level security;

-- Recreate INSERT policy correctly (INSERT uses only WITH CHECK)
do $$
begin
  if exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='label_events' and policyname='label_events_insert_auth'
  ) then
    drop policy label_events_insert_auth on public.label_events;
  end if;

  create policy label_events_insert_auth
    on public.label_events
    for insert
    to authenticated
    with check (true);
end$$;

-- SELECT policy keeps USING (valid for SELECT)
do $$
begin
  if exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='label_events' and policyname='label_events_select_auth'
  ) then
    drop policy label_events_select_auth on public.label_events;
  end if;

  create policy label_events_select_auth
    on public.label_events
    for select
    to authenticated
    using (true);
end$$;

-- Optional (dev): allow UPDATE/DELETE too
do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='label_events' and policyname='label_events_update_auth'
  ) then
    create policy label_events_update_auth
      on public.label_events
      for update
      to authenticated
      using (true)
      with check (true);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='label_events' and policyname='label_events_delete_auth'
  ) then
    create policy label_events_delete_auth
      on public.label_events
      for delete
      to authenticated
      using (true);
  end if;
end$$;

-- Refresh PostgREST cache (best-effort)
do $$
begin
  perform pg_notify('pgrst','reload schema');
exception when others then
  null;
end$$;
