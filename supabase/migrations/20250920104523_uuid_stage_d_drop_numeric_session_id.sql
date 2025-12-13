do $$
declare
  has_col boolean := exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='label_events' and column_name='session_id'
  );
  nulls int := 0;
  deps int := 0;
begin
  if not has_col then
    raise notice 'label_events.session_id already absent; nothing to do.';
    return;
  end if;

  select count(*) into nulls from public.label_events where session_uuid is null;
  if nulls > 0 then
    raise notice 'Found % rows with session_uuid IS NULL; skipping drop for safety.', nulls;
    return;
  end if;

  -- check for constraints referencing session_id
  select count(*) into deps
  from pg_constraint c
  join pg_attribute a on a.attnum = any(c.conkey) and a.attrelid = c.conrelid
  join pg_class t on t.oid = c.conrelid
  join pg_namespace n on n.oid = t.relnamespace
  where n.nspname='public' and t.relname='label_events' and a.attname='session_id';
  if deps > 0 then
    raise notice 'Found % constraints referencing session_id; skipping drop.', deps;
    return;
  end if;

  -- drop column
  alter table public.label_events drop column session_id;

  raise notice 'Dropped label_events.session_id. UUID-only linkage in effect.';
end $$;

-- Nudge PostgREST
do $$ begin perform pg_notify('pgrst','reload schema'); exception when others then null; end $$;
