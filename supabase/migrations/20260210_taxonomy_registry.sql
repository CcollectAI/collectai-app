-- Versioned Taxonomy Registry
-- Maintains category_id, subtype_id, and collections[] tags with version tracking.
-- Created: 2026-02-10

BEGIN;

-- ============================================================================
-- 1. Taxonomy registry table
--    Stores full taxonomy definitions per version with mapping rules
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.taxonomy_registry (
    version TEXT PRIMARY KEY,                -- e.g. 'v1.0', 'v1.1'
    categories JSONB NOT NULL,               -- [{category_id, display_name, subtypes: [{id, name}], collections: [str]}]
    mapping_rules JSONB NOT NULL,            -- [{pattern, category_id, confidence, rationale}]
    migration_from TEXT REFERENCES public.taxonomy_registry(version),
    migration_rules JSONB,                   -- [{from_category, to_category, condition}]
    effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deprecated_at TIMESTAMPTZ,
    created_by TEXT DEFAULT 'system',
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_taxonomy_registry_effective
    ON public.taxonomy_registry (effective_from DESC);

CREATE INDEX IF NOT EXISTS idx_taxonomy_registry_active
    ON public.taxonomy_registry (effective_from DESC)
    WHERE deprecated_at IS NULL;

COMMENT ON TABLE public.taxonomy_registry IS
    'Versioned taxonomy definitions with category, subtype, and mapping rules.';
COMMENT ON COLUMN public.taxonomy_registry.version IS
    'Semantic version string, e.g. v1.0, v1.1';
COMMENT ON COLUMN public.taxonomy_registry.categories IS
    'Array of category objects with subtypes and collections.';
COMMENT ON COLUMN public.taxonomy_registry.mapping_rules IS
    'Array of regex pattern rules used for automatic category classification.';
COMMENT ON COLUMN public.taxonomy_registry.migration_from IS
    'Parent version this was migrated from (NULL for initial version).';
COMMENT ON COLUMN public.taxonomy_registry.migration_rules IS
    'Rules describing how categories were remapped from parent version.';

-- ============================================================================
-- 2. RLS policies
-- ============================================================================
ALTER TABLE public.taxonomy_registry ENABLE ROW LEVEL SECURITY;

-- Service role: full access
CREATE POLICY "service_role_taxonomy_registry"
    ON public.taxonomy_registry
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

-- Authenticated users: read-only
CREATE POLICY "authenticated_read_taxonomy_registry"
    ON public.taxonomy_registry
    FOR SELECT TO authenticated
    USING (true);

-- Anonymous users: read-only (for public API endpoints)
CREATE POLICY "anon_read_taxonomy_registry"
    ON public.taxonomy_registry
    FOR SELECT TO anon
    USING (true);

COMMIT;
