-- Ensure model_registry exists and has a 'uri' column (idempotent)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname='model_registry' AND c.relkind='r'
  ) THEN
    CREATE TABLE public.model_registry (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      name text NOT NULL,
      version text NOT NULL,
      uri text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT model_registry_unique UNIQUE (name, version)
    );
  ELSE
    -- table exists; add column if missing
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='model_registry' AND column_name='uri'
    ) THEN
      ALTER TABLE public.model_registry ADD COLUMN uri text NOT NULL DEFAULT '';
      ALTER TABLE public.model_registry ALTER COLUMN uri DROP DEFAULT;
    END IF;
  END IF;
END $$;
