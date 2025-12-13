-- Ensure required columns exist on price_predictions (safe/idempotent)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='price_predictions' AND column_name='item_ref'
  ) THEN
    ALTER TABLE price_predictions ADD COLUMN item_ref text;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='price_predictions' AND column_name='category'
  ) THEN
    ALTER TABLE price_predictions ADD COLUMN category text;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='price_predictions' AND column_name='model_version'
  ) THEN
    ALTER TABLE price_predictions ADD COLUMN model_version text;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='price_predictions' AND column_name='q10'
  ) THEN
    ALTER TABLE price_predictions ADD COLUMN q10 numeric;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='price_predictions' AND column_name='q50'
  ) THEN
    ALTER TABLE price_predictions ADD COLUMN q50 numeric;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='price_predictions' AND column_name='q90'
  ) THEN
    ALTER TABLE price_predictions ADD COLUMN q90 numeric;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='price_predictions' AND column_name='confidence'
  ) THEN
    ALTER TABLE price_predictions ADD COLUMN confidence numeric;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='price_predictions' AND column_name='raw'
  ) THEN
    ALTER TABLE price_predictions ADD COLUMN raw jsonb;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='price_predictions' AND column_name='created_at'
  ) THEN
    ALTER TABLE price_predictions ADD COLUMN created_at timestamptz DEFAULT now();
  END IF;
END $$;

-- Create indexes if they don't exist
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE c.relkind='i' AND c.relname='pp_item_ref_idx'
  ) THEN
    CREATE INDEX pp_item_ref_idx ON price_predictions(item_ref);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE c.relkind='i' AND c.relname='pp_category_idx'
  ) THEN
    CREATE INDEX pp_category_idx ON price_predictions(category);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE c.relkind='i' AND c.relname='pp_created_idx'
  ) THEN
    CREATE INDEX pp_created_idx ON price_predictions(created_at);
  END IF;
END $$;
