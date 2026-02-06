-- Expand model_registry to support per-category ML models
-- Required by app/ml/model_loader.py which expects these columns
--
-- Existing cols: id, name, version, uri, created_at
-- Adding: category, model_type, s3_key, artifact_json, uncertainty_scale, is_active

DO $$
BEGIN
  -- category: which collectible category this model serves
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='model_registry' AND column_name='category'
  ) THEN
    ALTER TABLE public.model_registry ADD COLUMN category text;
  END IF;

  -- model_type: e.g. "ridge_v1", "xgboost_v1"
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='model_registry' AND column_name='model_type'
  ) THEN
    ALTER TABLE public.model_registry ADD COLUMN model_type text DEFAULT 'ridge_v1';
  END IF;

  -- s3_key: path to model artifact in S3 (alternative to inline artifact_json)
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='model_registry' AND column_name='s3_key'
  ) THEN
    ALTER TABLE public.model_registry ADD COLUMN s3_key text;
  END IF;

  -- artifact_json: inline model artifact (Ridge coefficients, standardizer, etc.)
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='model_registry' AND column_name='artifact_json'
  ) THEN
    ALTER TABLE public.model_registry ADD COLUMN artifact_json jsonb;
  END IF;

  -- uncertainty_scale: multiplier for prediction intervals
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='model_registry' AND column_name='uncertainty_scale'
  ) THEN
    ALTER TABLE public.model_registry ADD COLUMN uncertainty_scale numeric DEFAULT 1.0;
  END IF;

  -- is_active: only one active model per category at a time
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='model_registry' AND column_name='is_active'
  ) THEN
    ALTER TABLE public.model_registry ADD COLUMN is_active boolean DEFAULT false;
  END IF;
END $$;

-- Index for fast lookup by category + active status (used by model_loader.py)
CREATE INDEX IF NOT EXISTS idx_model_registry_category_active
  ON public.model_registry (category, is_active)
  WHERE is_active = true;
