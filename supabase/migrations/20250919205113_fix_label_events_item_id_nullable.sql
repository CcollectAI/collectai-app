-- Ensure table exists
create table if not exists public.label_events (
  id bigserial primary key,
  session_id bigint not null,
  corrected_title text,
  corrected_condition text,
  corrected_price_eur numeric(12,2),
  created_at timestamptz not null default now()
);

-- Add item_id if missing
do $$
begin
  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='label_events' and column_name='item_id'
  ) then
    alter table public.label_events add column item_id bigint;
  end if;
end$$;

-- Make item_id nullable (drop NOT NULL if present)
do $$
declare
  is_not_null boolean;
begin
  select (is_nullable = 'NO')
  into is_not_null
  from information_schema.columns
  where table_schema='public' and table_name='label_events' and column_name='item_id';

  if coalesce(is_not_null, false) then
    alter table public.label_events alter column item_id drop not null;
  end if;
end$$;

-- Optional: add FK to items table if one exists; otherwise skip
do $$
declare
  has_public_items boolean := (to_regclass('public.items') is not null);
  has_pc_items     boolean := (to_regclass('predictive_capture.items') is not null);
  con_exists       boolean := exists (select 1 from pg_constraint where conname='label_events_item_id_fkey');
begin
  if con_exists then
    alter table public.label_events drop constraint label_events_item_id_fkey;
  end if;

  if has_public_items then
    alter table public.label_events
      add constraint label_events_item_id_fkey
      foreign key (item_id) references public.items(id)
      on delete set null;
  elsif has_pc_items then
    alter table public.label_events
      add constraint label_events_item_id_fkey
      foreign key (item_id) references predictive_capture.items(id)
      on delete set null;
  else
    raise notice 'No items table found; leaving item_id without FK.';
  end if;
end$$;

-- Nudge PostgREST to reload schema; ignore if not supported
do $$
begin
  perform pg_notify('pgrst','reload schema');
exception when others then
  null;
end$$;
