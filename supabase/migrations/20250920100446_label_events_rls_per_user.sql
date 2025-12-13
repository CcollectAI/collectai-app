-- Enable RLS
alter table public.label_events enable row level security;

-- Drop old dev policies if present (names may vary; ignore errors)
do $$ begin
  if exists(select 1 from pg_policies where schemaname='public' and tablename='label_events' and policyname='label_events_insert_auth') then
    drop policy label_events_insert_auth on public.label_events;
  end if;
  if exists(select 1 from pg_policies where schemaname='public' and tablename='label_events' and policyname='label_events_select_auth') then
    drop policy label_events_select_auth on public.label_events;
  end if;
exception when others then null; end $$;

-- Strict per-user policies (owner-only)
create policy label_events_select_own
  on public.label_events
  for select
  to authenticated
  using (user_id = auth.uid());

create policy label_events_insert_own
  on public.label_events
  for insert
  to authenticated
  with check (user_id = auth.uid());

create policy label_events_update_own
  on public.label_events
  for update
  to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

create policy label_events_delete_own
  on public.label_events
  for delete
  to authenticated
  using (user_id = auth.uid());

-- Service role bypasses RLS automatically. Nudge schema cache:
do $$ begin perform pg_notify('pgrst','reload schema'); exception when others then null; end $$;
