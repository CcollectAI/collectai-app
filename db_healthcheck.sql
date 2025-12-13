select 'label_events exists' as check, to_regclass('public.label_events') is not null as ok;
select column_name from information_schema.columns where table_schema='public' and table_name='label_events'
  and column_name in ('session_id','action','corrected_title','corrected_condition','corrected_price_eur','created_at')
order by column_name;
