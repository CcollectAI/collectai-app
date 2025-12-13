-- Insert two sessions and grab the first one's id
with s1 as (
  insert into prediction_sessions (user_id, category, status)
  values (null, 'pokemon', 'done')
  returning id as session_id
), s2 as (
  insert into prediction_sessions (user_id, category, status)
  values (null, 'funko', 'pending')
  returning id
)
select 1;

-- Conditionally insert a label depending on which column name exists
do $$
declare
  sid bigint;
  col_session_id_exists boolean;
  col_prediction_session_id_exists boolean;
begin
  -- fetch the id from the most recent 'done' session
  select id into sid
  from prediction_sessions
  where status = 'done'
  order by id desc
  limit 1;

  -- check schema
  select exists(
    select 1 from information_schema.columns
    where table_name='label_events' and column_name='session_id'
  ) into col_session_id_exists;

  select exists(
    select 1 from information_schema.columns
    where table_name='label_events' and column_name='prediction_session_id'
  ) into col_prediction_session_id_exists;

  if col_session_id_exists then
    -- label_events(session_id, ...)
    insert into label_events (session_id, corrected_title, corrected_condition, corrected_price_eur)
    values (sid, 'Test Card', 'Near Mint', 123);
  elsif col_prediction_session_id_exists then
    -- label_events(prediction_session_id, ...)
    insert into label_events (prediction_session_id, corrected_title, corrected_condition, corrected_price_eur)
    values (sid, 'Test Card', 'Near Mint', 123);
  else
    raise notice 'Skipping label_events seed: no session id column found.';
  end if;
end $$;
