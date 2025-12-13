-- 1) Create enum if missing
do $$
begin
  if not exists (select 1 from pg_type where typname = 'card_condition') then
    create type card_condition as enum ('Sealed','Mint','Near Mint','Good','Fair','Poor');
  end if;
end$$;

-- 2) Ensure column exists
alter table public.label_events
  add column if not exists corrected_condition text;

-- 3) Backfill any nulls before NOT NULL/default
update public.label_events set corrected_condition = 'Near Mint' where corrected_condition is null;

-- 4) Convert to enum with default
alter table public.label_events
  alter column corrected_condition drop default,
  alter column corrected_condition type card_condition using corrected_condition::card_condition,
  alter column corrected_condition set default 'Near Mint'::card_condition,
  alter column corrected_condition set not null;

-- 5) Refresh PostgREST (best effort)
do $$
begin
  perform pg_notify('pgrst','reload schema');
exception when others then
  null;
end$$;
