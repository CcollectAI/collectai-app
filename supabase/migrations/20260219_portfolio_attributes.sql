-- ============================================================================
-- Migration: 20260219_portfolio_attributes.sql
-- Purpose:   Add attributes_json JSONB column to portfolio_items for
--            category-specific detail fields (e.g., rarity, grade, set).
-- Safe:      Uses IF NOT EXISTS / ADD COLUMN IF NOT EXISTS.
-- ============================================================================

BEGIN;

-- Add attributes_json column if it doesn't exist yet
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'portfolio_items'
      AND column_name = 'attributes_json'
  ) THEN
    ALTER TABLE public.portfolio_items
      ADD COLUMN attributes_json jsonb DEFAULT NULL;
  END IF;
END $$;

-- Create a GIN index for efficient JSONB queries on attributes
CREATE INDEX IF NOT EXISTS idx_portfolio_items_attributes
  ON public.portfolio_items USING gin (attributes_json)
  WHERE attributes_json IS NOT NULL;

COMMIT;
