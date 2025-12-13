-- Phase 1: Add a new uuid column and backfill where possible; keep old column intact
ALTER TABLE public.label_events
  ADD COLUMN IF NOT EXISTS session_id_uuid uuid;

-- Try to backfill from text form if it looks like a UUID
UPDATE public.label_events
SET session_id_uuid = NULLIF(session_id::text, '')::uuid
WHERE session_id_uuid IS NULL
  AND session_id::text ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$';

-- (Stop here for manual review; once clean we can swap columns in Phase 2)
