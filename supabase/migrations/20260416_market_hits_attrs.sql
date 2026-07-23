-- R50k: Marketplace attribute extraction — data flywheel.
-- Adds `attrs` JSONB column to market_hits to capture structured listing
-- attributes (item specifics, tags, grades, references) from marketplace
-- adapters. Aggregated into category_items.attributes_json.market_observed
-- by workers/aggregate_catalog_attributes.py.

ALTER TABLE public.market_hits
  ADD COLUMN IF NOT EXISTS attrs JSONB NOT NULL DEFAULT '{}'::jsonb;

-- Reload PostgREST schema cache so API picks up the new column immediately
-- (avoids the 10-minute cache-miss trap, see learnings.md #71.3)
NOTIFY pgrst, 'reload schema';
