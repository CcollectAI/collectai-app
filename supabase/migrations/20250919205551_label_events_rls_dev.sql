-- Fixed: INSERT policy must use only WITH CHECK (no USING)
-- Idempotent: drops existing policies if present, then recreates.

alter table public.label_events enable row level security;

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

-- Optional dev-friendly policies (update/delete). Safe to keep or remove.
do $$
begin
  if exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='label_events' and policyname='label_events_update_auth'
  ) then
    drop policy label_events_update_auth on public.label_events;
  end if;

  create policy label_events_update_auth
    on public.label_events
    for update
    to authenticated
    using (true)
    with check (true);

  if exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='label_events' and policyname='label_events_delete_auth'
  ) then
    drop policy label_events_delete_auth on public.label_events;
  end if;

  create policy label_events_delete_auth
    on public.label_events
    for delete
    to authenticated
    using (true);
end$$;

-- Refresh PostgREST cache (best-effort)
do $$
begin
  perform pg_notify('pgrst','reload schema');
exception when others then
  null;
end$$;
