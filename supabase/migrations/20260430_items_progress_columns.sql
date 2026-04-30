-- Add progress-tracking columns to items so the catalog browser
-- progress endpoints (PATCH/GET /items/{id}/progress) work.
-- These columns were referenced by code but never migrated; the
-- endpoints 500'd with `column "progress_status" does not exist`.

ALTER TABLE public.items
  ADD COLUMN IF NOT EXISTS progress_status text,
  ADD COLUMN IF NOT EXISTS progress_pct integer,
  ADD COLUMN IF NOT EXISTS progress_notes text;
