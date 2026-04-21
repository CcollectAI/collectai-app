-- Event quality safeguards — Phase 1 columns
-- Design in docs/EVENT_QUALITY_PLAN.md
-- Both columns are nullable so ingest/backfill can happen in any order.

ALTER TABLE public.events
  ADD COLUMN IF NOT EXISTS trust_tier    text,
  ADD COLUMN IF NOT EXISTS quality_score int;

-- Partial indexes only on populated rows; keeps cold-storage free.
CREATE INDEX IF NOT EXISTS idx_events_trust_tier
  ON public.events (trust_tier)
  WHERE trust_tier IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_events_quality_score
  ON public.events (quality_score)
  WHERE quality_score IS NOT NULL;

-- Soft sanity bounds — don't throw, just clamp via future writer logic.
-- No CHECK constraint here yet; Phase 1 shakes out the score distribution
-- before we lock down a range (see DATA_SCALING_PLAN §6).
