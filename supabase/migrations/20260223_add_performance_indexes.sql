-- Performance indexes for frequently queried columns
-- 2026-02-23: Added based on query audit
--
-- NOTE: Several proposed indexes were skipped because equivalent coverage
-- already exists in earlier migrations:
--   - events(created_by)                → idx_events_created_by (20260209)
--   - event_announcements(event_id)     → idx_event_announcements_event (20260222)
--   - build_paint_projects(category_id) → idx_build_paint_projects_category (20260222)
--   - build_paint_projects(item_id)     → idx_build_paint_projects_item (20260222)
--   - activity_feed(user_id,created_at) → idx_activity_feed_user (20260222)

-- event_attendees queries by (event_id, status) for capacity checks and RSVP counts.
-- The PK covers (event_id, user_id) but status-filtered aggregations need this.
CREATE INDEX IF NOT EXISTS idx_event_attendees_event_id_status
  ON event_attendees(event_id, status);

-- sponsor_companies queries by admin_user_id for "my companies" listing
CREATE INDEX IF NOT EXISTS idx_sponsor_companies_admin_user_id
  ON sponsor_companies(admin_user_id);
