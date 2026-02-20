-- Catalog Learning System
-- Captures every "miss" across all input methods (barcode, photo, manual, URL)
-- and surfaces new category candidates from real user behavior.

-- ---------------------------------------------------------------------------
-- Enable pg_trgm for fuzzy name matching (idempotent)
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ---------------------------------------------------------------------------
-- catalog_suggestions — every unmapped item signal
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS catalog_suggestions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    source          TEXT NOT NULL CHECK (source IN ('barcode', 'photo', 'manual', 'url')),
    input_data      JSONB NOT NULL DEFAULT '{}',
    suggested_name  TEXT NOT NULL,
    suggested_category TEXT,                  -- existing slug or free-text
    matched_category TEXT,                    -- set when auto-mapped
    confidence      REAL DEFAULT 0.0,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'mapped', 'rejected', 'new_category')),
    mapped_item_key TEXT,                     -- set when auto-mapped to a catalog item
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Unique constraint: prevent duplicate submissions per user+source+input
CREATE UNIQUE INDEX IF NOT EXISTS uq_catalog_suggestions_dedup
    ON catalog_suggestions (user_id, source, md5(input_data::text));

-- Query indexes
CREATE INDEX IF NOT EXISTS idx_catalog_suggestions_status_created
    ON catalog_suggestions (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_catalog_suggestions_user
    ON catalog_suggestions (user_id);
CREATE INDEX IF NOT EXISTS idx_catalog_suggestions_category
    ON catalog_suggestions (suggested_category);

-- Trigram index for fuzzy name matching
CREATE INDEX IF NOT EXISTS idx_catalog_suggestions_name_trgm
    ON catalog_suggestions USING gin (suggested_name gin_trgm_ops);

-- RLS
ALTER TABLE catalog_suggestions ENABLE ROW LEVEL SECURITY;

-- Users can INSERT their own suggestions
CREATE POLICY catalog_suggestions_insert ON catalog_suggestions
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = user_id);

-- Users can SELECT their own suggestions
CREATE POLICY catalog_suggestions_select ON catalog_suggestions
    FOR SELECT TO authenticated
    USING (auth.uid() = user_id);

-- Service role has full access
CREATE POLICY catalog_suggestions_service ON catalog_suggestions
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

-- ---------------------------------------------------------------------------
-- category_candidates — aggregated new category proposals
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS category_candidates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposed_name   TEXT NOT NULL,
    proposed_slug   TEXT NOT NULL UNIQUE,
    description     TEXT,
    signal_count    INTEGER NOT NULL DEFAULT 0,
    unique_users    INTEGER NOT NULL DEFAULT 0,
    first_seen      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen       TIMESTAMPTZ NOT NULL DEFAULT now(),
    status          TEXT NOT NULL DEFAULT 'watching'
                    CHECK (status IN ('watching', 'candidate', 'approved', 'rejected')),
    admin_notes     TEXT
);

-- RLS: service role only (admin-facing)
ALTER TABLE category_candidates ENABLE ROW LEVEL SECURITY;

CREATE POLICY category_candidates_service ON category_candidates
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

-- updated_at trigger for catalog_suggestions
CREATE OR REPLACE FUNCTION catalog_suggestions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_catalog_suggestions_updated_at
    BEFORE UPDATE ON catalog_suggestions
    FOR EACH ROW
    EXECUTE FUNCTION catalog_suggestions_updated_at();
