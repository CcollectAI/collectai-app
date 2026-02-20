-- Additional indexes for catalog_learning_worker performance.
-- The worker aggregates by (lower(suggested_name), suggested_category) and
-- filters on status + suggested_category IS NOT NULL frequently.

-- Composite index for the auto-map consensus query (Step 1 of worker)
CREATE INDEX IF NOT EXISTS idx_catalog_suggestions_pending_category
    ON catalog_suggestions (status, suggested_category)
    WHERE status = 'pending' AND suggested_category IS NOT NULL;

-- Index for the free-text category candidate query (Step 2 of worker)
CREATE INDEX IF NOT EXISTS idx_catalog_suggestions_new_category
    ON catalog_suggestions (status, suggested_category)
    WHERE status IN ('pending', 'new_category') AND suggested_category IS NOT NULL;

-- Index on category_candidates status for promotion query (Step 3)
CREATE INDEX IF NOT EXISTS idx_category_candidates_status
    ON category_candidates (status, unique_users)
    WHERE status = 'watching';
