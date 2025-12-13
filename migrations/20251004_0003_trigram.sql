CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_watchlist_nk_trgm ON watchlist USING gin (nk gin_trgm_ops);
