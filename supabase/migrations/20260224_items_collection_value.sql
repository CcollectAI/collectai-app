-- Add missing columns to items table for collection_name and estimated_value persistence
ALTER TABLE items ADD COLUMN IF NOT EXISTS collection_name text;
ALTER TABLE items ADD COLUMN IF NOT EXISTS estimated_value numeric;
