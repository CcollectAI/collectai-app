-- Extensions present?
select 'pg_trgm' as ext, installed from (
  select exists(select 1 from pg_extension where extname='pg_trgm') as installed
) x;

-- Core tables present?
select 'items' as tbl, to_regclass('public.items') is not null as present
union all
select 'market_hits', to_regclass('public.market_hits') is not null
union all
select 'price_predictions', to_regclass('public.price_predictions') is not null
union all
select 'watchlist', to_regclass('public.watchlist') is not null
union all
select 'events', to_regclass('public.events') is not null
union all
select 'feedback', to_regclass('public.feedback') is not null;

-- Key indexes present?
select indexname from pg_indexes
where schemaname='public'
and indexname in (
  'idx_items_user','idx_items_category','idx_items_normalized_key',
  'idx_mh_provider_listing','idx_mh_ended_at','idx_mh_normkey','idx_mh_title_lower',
  'idx_pp_item_asof'
)
order by 1;
