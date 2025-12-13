-- Ensure model_registry is a real table and has 'uri'
DO $$
BEGIN
  -- if a VIEW with the same name exists, drop it (safe only if you intended a table)
  IF EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname='model_registry' AND c.relkind='v'
  ) THEN
    DROP VIEW public.model_registry;
  END IF;

  -- create table if missing
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
  END IF;

  -- add 'uri' column if the table exists but lacks it
  IF EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname='model_registry' AND c.relkind='r'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='model_registry' AND column_name='uri'
  ) THEN
    ALTER TABLE public.model_registry ADD COLUMN uri text NOT NULL DEFAULT '';
    ALTER TABLE public.model_registry ALTER COLUMN uri DROP DEFAULT;
  END IF;
END $$;
