-- Ensure table exists (no-op if it does)
create table if not exists public.label_events (
  id bigserial primary key,
  session_id bigint not null,
  corrected_title text,
  corrected_condition text,
  corrected_price_eur numeric(12,2),
  -- we add/normalize these below if missing/different
  created_at timestamptz not null default now()
);

-- Ensure 'action' column exists and is text
do $$
declare
  col_type text;
begin
  -- add if missing
  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='label_events' and column_name='action'
  ) then
    alter table public.label_events add column action text;
  end if;

  -- make sure it's text (if it isn't, try to cast)
  select data_type into col_type
  from information_schema.columns
  where table_schema='public' and table_name='label_events' and column_name='action';

  if col_type <> 'text' then
    alter table public.label_events
      alter column action type text using action::text;
  end if;

  -- backfill nulls to 'label' (so we can set NOT NULL)
  update public.label_events set action = 'label' where action is null;

  -- set default going forward
  alter table public.label_events alter column action set default 'label';

  -- enforce NOT NULL
  alter table public.label_events alter column action set not null;
end$$;

-- Nudge PostgREST to reload schema (ignore if not supported)
do $$
begin
  perform pg_notify('pgrst','reload schema');
exception when others then
  null;
end$$;
