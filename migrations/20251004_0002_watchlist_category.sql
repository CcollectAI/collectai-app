ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS category text;
CREATE INDEX IF NOT EXISTS idx_watchlist_user_category ON watchlist(user_id, category);
