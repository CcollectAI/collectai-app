-- Weak labels from market_observations (sold EUR only)
create or replace view public.v_market_dataset as
select
  provider||'-'||source_id as sample_id,
  title,
  category,
  coalesce(condition,'Unknown') as condition,
  price_eur as label_value_eur,
  image_url,
  provider as source,
  'obs' as version,
  observed_at as created_at
from public.market_observations
where is_sold = true and price_eur is not null;

-- Union with your curated training_items view
create or replace view public.v_training_dataset_union as
select * from public.v_training_dataset
union all
select * from public.v_market_dataset;
