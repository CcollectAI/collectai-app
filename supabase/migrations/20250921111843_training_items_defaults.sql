alter table public.training_items
  add column if not exists attributes jsonb;

update public.training_items set attributes = '{}'::jsonb where attributes is null;
alter table public.training_items alter column attributes set default '{}'::jsonb;
