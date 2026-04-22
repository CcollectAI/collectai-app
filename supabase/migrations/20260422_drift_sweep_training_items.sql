-- 2026-04-22: drift sweep batch 3 — training_items missing 4 columns.
-- training_items already has corrected_title / corrected_condition /
-- corrected_price_eur (clearly mid-feature schema), but feedback_router
-- expects 4 sibling columns that were never created.

ALTER TABLE public.training_items
  ADD COLUMN IF NOT EXISTS corrected_category    text,
  ADD COLUMN IF NOT EXISTS corrected_attributes  jsonb,
  ADD COLUMN IF NOT EXISTS correction_notes      text,
  ADD COLUMN IF NOT EXISTS corrected_at          timestamptz;

-- Index supports the "recent corrections" feed (ORDER BY corrected_at DESC).
CREATE INDEX IF NOT EXISTS idx_training_items_corrected_at
  ON public.training_items (corrected_at DESC NULLS LAST)
  WHERE corrected_at IS NOT NULL;
