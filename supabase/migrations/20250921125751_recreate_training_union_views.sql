-- Ensure base curated view exists
DROP VIEW IF EXISTS public.v_training_dataset;
CREATE VIEW public.v_training_dataset AS
SELECT
  COALESCE(idem_key, 'ti-' || id)           AS sample_id,
  COALESCE(title, attributes->>'title')     AS title,
  attributes->>'category'                   AS category,
  attributes->>'condition'                  AS condition,
  (attributes->>'final_value_eur')::numeric AS label_value_eur,
  image_url,
  source,
  version,
  created_at
FROM public.training_items;

-- Weak-label observations (if table exists)
DROP VIEW IF EXISTS public.v_market_dataset;
CREATE VIEW public.v_market_dataset AS
SELECT
  provider || '-' || source_id              AS sample_id,
  title,
  category,
  COALESCE(condition, 'Unknown')            AS condition,
  price_eur                                 AS label_value_eur,
  image_url,
  provider                                  AS source,
  'obs'                                     AS version,
  observed_at                               AS created_at
FROM public.market_observations
WHERE is_sold = TRUE AND price_eur IS NOT NULL;

-- Union of curated + observations
DROP VIEW IF EXISTS public.v_training_dataset_union;
CREATE VIEW public.v_training_dataset_union AS
SELECT * FROM public.v_training_dataset
UNION ALL
SELECT * FROM public.v_market_dataset;
