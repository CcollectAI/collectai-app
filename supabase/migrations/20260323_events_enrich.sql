-- ============================================================================
-- Migration: Add franchise_id, latitude, longitude to events table
-- Date: 2026-03-23
--
-- Enables:
--   1. Franchise-aware event discovery (Star Wars, Marvel, HP, LOTR, etc.)
--   2. Location-based event search (nearby events via lat/lon)
-- ============================================================================

-- Add franchise_id column
ALTER TABLE public.events
  ADD COLUMN IF NOT EXISTS franchise_id text;

-- Add geocoding columns
ALTER TABLE public.events
  ADD COLUMN IF NOT EXISTS latitude double precision;

ALTER TABLE public.events
  ADD COLUMN IF NOT EXISTS longitude double precision;

-- Index for franchise-based queries
CREATE INDEX IF NOT EXISTS idx_events_franchise_id
  ON public.events(franchise_id)
  WHERE franchise_id IS NOT NULL;

-- Index for location-based queries (simple lat/lon range)
CREATE INDEX IF NOT EXISTS idx_events_geo
  ON public.events(latitude, longitude)
  WHERE latitude IS NOT NULL AND longitude IS NOT NULL;

-- Index for nearby events (date + geo combined)
CREATE INDEX IF NOT EXISTS idx_events_date_geo
  ON public.events(date, latitude, longitude)
  WHERE latitude IS NOT NULL AND longitude IS NOT NULL;
