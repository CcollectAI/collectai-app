-- Additional performance indexes
-- user_category_follows: speed up category follow lookups
CREATE INDEX IF NOT EXISTS idx_user_category_follows_category_id
    ON user_category_follows (category_id);

-- events: speed up "my events" queries
CREATE INDEX IF NOT EXISTS idx_events_created_by
    ON events (created_by);
