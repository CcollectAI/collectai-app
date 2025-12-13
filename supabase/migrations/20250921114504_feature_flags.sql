create table if not exists public.feature_flags (
  key text primary key,
  value boolean not null default false,
  updated_at timestamptz not null default now()
);
alter table public.feature_flags enable row level security;
do $$ begin
  if not exists (
    select 1 from pg_policies where schemaname='public' and tablename='feature_flags' and policyname='auth_read_flags'
  ) then
    execute 'create policy "auth_read_flags" on public.feature_flags for select to authenticated using (true)';
  end if;
end $$;

insert into public.feature_flags(key, value)
  values ('ebayReal', false)
on conflict (key) do nothing;
