alter table public.label_events enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies where schemaname='public' and tablename='label_events'
      and policyname='auth_read_label_events'
  ) then
    execute 'create policy "auth_read_label_events"
             on public.label_events for select to authenticated using (true)';
  end if;
end$$;
