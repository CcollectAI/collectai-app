-- enum + migrate action -> enum with default
do $$
begin
  if not exists (select 1 from pg_type where typname = 'label_action') then
    create type label_action as enum ('label','correction','confirm');
  end if;
end$$;

alter table public.label_events
  alter column action drop default,
  alter column action type label_action using action::label_action,
  alter column action set default 'label'::label_action,
  alter column action set not null;
