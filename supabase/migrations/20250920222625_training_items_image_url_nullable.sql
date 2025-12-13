-- Ensure training_items.image_url exists and is nullable
do $$
begin
  -- add column if it doesn't exist
  if not exists (
    select 1
    from information_schema.columns
    where table_schema='public' and table_name='training_items' and column_name='image_url'
  ) then
    alter table public.training_items add column image_url text;
  end if;

  -- drop NOT NULL if present
  if exists (
    select 1
    from information_schema.columns
    where table_schema='public' and table_name='training_items'
      and column_name='image_url' and is_nullable='NO'
  ) then
    alter table public.training_items alter column image_url drop not null;
  end if;
end$$;

-- Nudge PostgREST
notify pgrst, 'reload schema';
