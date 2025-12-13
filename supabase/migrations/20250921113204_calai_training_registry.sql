-- dataset export view (join training_items -> flattened fields commonly used)
DROP VIEW IF EXISTS public.v_training_dataset;

CREATE VIEW public.v_training_dataset AS
SELECT
  COALESCE(idem_key, 'ti-' || id)                 AS sample_id,
  COALESCE(title, attributes->>'title')           AS title,
  attributes->>'category'                         AS category,
  attributes->>'condition'                        AS condition,
  (attributes->>'final_value_eur')::numeric       AS label_value_eur,
  image_url,
  source,
  version,
  created_at
FROM public.training_items;

-- model registry table (idempotent)
CREATE TABLE IF NOT EXISTS public.model_registry (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  version TEXT NOT NULL,
  uri TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(name, version)
);
