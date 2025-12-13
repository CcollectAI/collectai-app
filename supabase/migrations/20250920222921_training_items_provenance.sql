do $$
begin
  if not exists(select 1 from information_schema.columns where table_schema='public' and table_name='training_items' and column_name='source') then
    alter table public.training_items add column source text;
  end if;
  if not exists(select 1 from information_schema.columns where table_schema='public' and table_name='training_items' and column_name='idem_key') then
    alter table public.training_items add column idem_key text;
  end if;
  if not exists(select 1 from information_schema.columns where table_schema='public' and table_name='training_items' and column_name='version') then
    alter table public.training_items add column version text;
  end if;
end$$;

-- unique constraint on idem_key (nulls distinct)
create unique index if not exists training_items_idem_key_key
  on public.training_items(idem_key) where idem_key is not null;

notify pgrst, 'reload schema';
