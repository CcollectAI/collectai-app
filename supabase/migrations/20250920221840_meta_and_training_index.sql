-- Helper views to inspect schema via REST (public schema only)

create or replace view public.meta_training_items_columns as
select column_name, is_nullable, data_type
from information_schema.columns
where table_schema = 'public' and table_name = 'training_items';

create or replace view public.meta_training_items_indexes as
select indexname, indexdef
from pg_indexes
where schemaname = 'public' and tablename = 'training_items';

-- Make sure we have a unique/PK on session_uuid for upsert patterns
do $$
begin
  if not exists (
    select 1
    from pg_indexes
    where schemaname='public' and tablename='training_items' and indexname='training_items_session_uuid_key'
  ) then
    create unique index training_items_session_uuid_key
      on public.training_items(session_uuid);
  end if;
end$$;

-- Nudge PostgREST
notify pgrst, 'reload schema';
