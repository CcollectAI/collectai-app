-- 2026-04-22: items table missing 3 columns the modern items_router writes
-- and reads. Surfaced by the HTTP smoke test — GET /items, POST /items,
-- and the DELETE path all reference these columns, so every items endpoint
-- 500'd before this migration.

ALTER TABLE public.items
  ADD COLUMN IF NOT EXISTS collection_name  text,
  ADD COLUMN IF NOT EXISTS estimated_value  numeric,
  ADD COLUMN IF NOT EXISTS updated_at       timestamptz NOT NULL DEFAULT now();

-- Cursor pagination orders by (updated_at DESC, id DESC) — index supports it.
CREATE INDEX IF NOT EXISTS idx_items_user_updated_at
  ON public.items (user_id, updated_at DESC, id DESC);

-- Auto-bump updated_at on every UPDATE so cursor pagination stays accurate.
CREATE OR REPLACE FUNCTION public.items_set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'items_set_updated_at_trg'
  ) THEN
    CREATE TRIGGER items_set_updated_at_trg
      BEFORE UPDATE ON public.items
      FOR EACH ROW EXECUTE FUNCTION public.items_set_updated_at();
  END IF;
END $$;

-- Backfill updated_at = created_at for existing rows so cursor pagination
-- doesn't put every legacy row at "now()".
UPDATE public.items SET updated_at = created_at WHERE updated_at IS NULL OR updated_at = created_at;
