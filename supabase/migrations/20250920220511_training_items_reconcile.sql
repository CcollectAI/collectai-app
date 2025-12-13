create extension if not exists pgcrypto;

-- 1) Table (create if not exists)
create table if not exists public.training_items (
  session_uuid uuid primary key,              -- unique per session
  user_id uuid,
  category text,
  title text,                                 -- legacy display; nullable
  raw_title text,
  raw_condition text,
  raw_price_eur numeric(12,2),
  corrected_title text,
  corrected_condition text,
  corrected_price_eur numeric(12,2),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- 2) Add any missing columns safely
do $$
begin
  if not exists (select 1 from information_schema.columns
    where table_schema='public' and table_name='training_items' and column_name='session_uuid') then
    alter table public.training_items add column session_uuid uuid;
  end if;
  if not exists (select 1 from information_schema.columns
    where table_schema='public' and table_name='training_items' and column_name='user_id') then
    alter table public.training_items add column user_id uuid;
  end if;
  if not exists (select 1 from information_schema.columns
    where table_schema='public' and table_name='training_items' and column_name='category') then
    alter table public.training_items add column category text;
  end if;
  if not exists (select 1 from information_schema.columns
    where table_schema='public' and table_name='training_items' and column_name='title') then
    alter table public.training_items add column title text;
  end if;
  if not exists (select 1 from information_schema.columns
    where table_schema='public' and table_name='training_items' and column_name='raw_title') then
    alter table public.training_items add column raw_title text;
  end if;
  if not exists (select 1 from information_schema.columns
    where table_schema='public' and table_name='training_items' and column_name='raw_condition') then
    alter table public.training_items add column raw_condition text;
  end if;
  if not exists (select 1 from information_schema.columns
    where table_schema='public' and table_name='training_items' and column_name='raw_price_eur') then
    alter table public.training_items add column raw_price_eur numeric(12,2);
  end if;
  if not exists (select 1 from information_schema.columns
    where table_schema='public' and table_name='training_items' and column_name='corrected_title') then
    alter table public.training_items add column corrected_title text;
  end if;
  if not exists (select 1 from information_schema.columns
    where table_schema='public' and table_name='training_items' and column_name='corrected_condition') then
    alter table public.training_items add column corrected_condition text;
  end if;
  if not exists (select 1 from information_schema.columns
    where table_schema='public' and table_name='training_items' and column_name='corrected_price_eur') then
    alter table public.training_items add column corrected_price_eur numeric(12,2);
  end if;
  if not exists (select 1 from information_schema.columns
    where table_schema='public' and table_name='training_items' and column_name='created_at') then
    alter table public.training_items add column created_at timestamptz not null default now();
  end if;
  if not exists (select 1 from information_schema.columns
    where table_schema='public' and table_name='training_items' and column_name='updated_at') then
    alter table public.training_items add column updated_at timestamptz not null default now();
  end if;
end$$;

-- 3) Ensure title is nullable (legacy schemas sometimes made it NOT NULL)
do $$
declare v_is_nullable text;
begin
  select c.is_nullable into v_is_nullable
  from information_schema.columns c
  where c.table_schema='public' and c.table_name='training_items' and c.column_name='title';
  if v_is_nullable = 'NO' then
    alter table public.training_items alter column title drop not null;
  end if;
end$$;

-- 4) Ensure PK/unique on session_uuid (supports upsert)
do $$
begin
  -- if no PK, add it; otherwise ensure unique index
  if not exists (
    select 1 from information_schema.table_constraints
    where table_schema='public' and table_name='training_items'
      and constraint_type in ('PRIMARY KEY','UNIQUE')
  ) then
    alter table public.training_items add constraint training_items_session_uuid_key unique (session_uuid);
  end if;
end$$;

-- 5) Backfill title where missing
update public.training_items
set title = coalesce(corrected_title, raw_title)
where title is null and (corrected_title is not null or raw_title is not null);

-- 6) touch updated_at trigger
create or replace function public.trg_touch_updated_at() returns trigger
language plpgsql as $$
begin
  new.updated_at := now();
  return new;
end$$;

drop trigger if exists trg_training_items_touch on public.training_items;
create trigger trg_training_items_touch
before update on public.training_items
for each row execute function public.trg_touch_updated_at();

-- 7) auto-fill title trigger
create or replace function public.trg_training_items_fill_title()
returns trigger language plpgsql as $$
begin
  new.title := coalesce(new.corrected_title, new.raw_title, new.title);
  return new;
end$$;

drop trigger if exists trg_training_items_fill_title_biu on public.training_items;
create trigger trg_training_items_fill_title_biu
before insert or update of corrected_title, raw_title, title
on public.training_items
for each row execute function public.trg_training_items_fill_title();

-- 8) RLS policies (owner-only)
alter table public.training_items enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='training_items' and policyname='training_items_select_own'
  ) then
    create policy training_items_select_own
      on public.training_items for select to authenticated
      using (user_id = auth.uid());
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='training_items' and policyname='training_items_insert_own'
  ) then
    create policy training_items_insert_own
      on public.training_items for insert to authenticated
      with check (user_id = auth.uid());
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname='public' and tablename='training_items' and policyname='training_items_update_own'
  ) then
    create policy training_items_update_own
      on public.training_items for update to authenticated
      using (user_id = auth.uid())
      with check (user_id = auth.uid());
  end if;
end$$;

-- 9) Nudge PostgREST
notify pgrst, 'reload schema';
