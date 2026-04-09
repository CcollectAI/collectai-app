-- Add build/paint status and fraud fields to items table
ALTER TABLE public.items
    ADD COLUMN IF NOT EXISTS build_state text,
    ADD COLUMN IF NOT EXISTS paint_state text,
    ADD COLUMN IF NOT EXISTS build_notes text,
    ADD COLUMN IF NOT EXISTS date_started timestamptz,
    ADD COLUMN IF NOT EXISTS date_completed timestamptz,
    ADD COLUMN IF NOT EXISTS authenticity_score numeric,
    ADD COLUMN IF NOT EXISTS fraud_flags text[],
    ADD COLUMN IF NOT EXISTS fraud_details jsonb;

-- Optional: simple constraint to keep build_state values sane
ALTER TABLE public.items
    ADD CONSTRAINT IF NOT EXISTS items_build_state_check
    CHECK (
      build_state IS NULL OR build_state IN (
        'unbuilt',
        'in_progress',
        'snap_built',
        'primed',
        'basecoated',
        'painted_wip',
        'finished',
        'varnished',
        'custom_mod'
      )
    );
