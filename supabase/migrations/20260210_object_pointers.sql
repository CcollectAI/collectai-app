-- ==========================================================================
-- 20260210_object_pointers.sql
-- S3 data lake object pointer table for CollectAI
-- Tracks all S3 objects (catalog images, user photos, market dumps,
-- embeddings, training data) with metadata and content hashes.
-- ==========================================================================

CREATE TABLE IF NOT EXISTS public.object_pointers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    s3_key          TEXT NOT NULL UNIQUE,
    bucket          TEXT NOT NULL DEFAULT 'collectai-artifacts',
    content_hash    TEXT,                                       -- SHA256 of content
    size_bytes      BIGINT,
    content_type    TEXT,                                       -- e.g. 'image/jpeg', 'application/jsonl+gzip'
    object_type     TEXT NOT NULL,                              -- 'catalog_image', 'user_photo', 'market_dump', 'embedding', 'training_data'
    related_item_id TEXT,
    related_category TEXT,
    created_by      TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,                               -- soft delete timestamp
    metadata        JSONB DEFAULT '{}'::JSONB
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_object_pointers_type
    ON public.object_pointers (object_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_object_pointers_item
    ON public.object_pointers (related_item_id)
    WHERE related_item_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_object_pointers_s3key
    ON public.object_pointers (s3_key);

CREATE INDEX IF NOT EXISTS idx_object_pointers_deleted
    ON public.object_pointers (deleted_at)
    WHERE deleted_at IS NULL;

-- ==========================================================================
-- RLS policies
-- ==========================================================================

ALTER TABLE public.object_pointers ENABLE ROW LEVEL SECURITY;

-- service_role: full access (used by backend / pipelines)
CREATE POLICY object_pointers_service_all
    ON public.object_pointers
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- authenticated users: SELECT on their own items only
CREATE POLICY object_pointers_auth_select
    ON public.object_pointers
    FOR SELECT
    TO authenticated
    USING (created_by = auth.uid()::TEXT);
