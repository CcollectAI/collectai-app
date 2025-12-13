do $$
begin
  if not exists (select 1 from information_schema.columns where table_schema='public' and table_name='training_items' and column_name='quality') then
    alter table public.training_items add column quality text;
  end if;
  if not exists (select 1 from information_schema.columns where table_schema='public' and table_name='training_items' and column_name='notes') then
    alter table public.training_items add column notes text;
  end if;
  if not exists (select 1 from information_schema.columns where table_schema='public' and table_name='training_items' and column_name='reviewed_at') then
    alter table public.training_items add column reviewed_at timestamptz;
  end if;
  if not exists (select 1 from information_schema.columns where table_schema='public' and table_name='training_items' and column_name='reviewed_by') then
    alter table public.training_items add column reviewed_by uuid;
  end if;
end$$;
notify pgrst, 'reload schema';
