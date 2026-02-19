-- Sponsored Events — add sponsorship columns to events + analytics table
-- Migration: 20260219_sponsored_events.sql

-- ---------------------------------------------------------------------------
-- 1. Add sponsor columns to events table
-- ---------------------------------------------------------------------------

ALTER TABLE events ADD COLUMN IF NOT EXISTS is_sponsored BOOLEAN DEFAULT FALSE;
ALTER TABLE events ADD COLUMN IF NOT EXISTS sponsor_name TEXT;
ALTER TABLE events ADD COLUMN IF NOT EXISTS sponsor_logo_url TEXT;
ALTER TABLE events ADD COLUMN IF NOT EXISTS sponsor_tier TEXT
    CHECK (sponsor_tier IS NULL OR sponsor_tier IN ('featured', 'promoted', 'spotlight'));
ALTER TABLE events ADD COLUMN IF NOT EXISTS sponsor_paid_at TIMESTAMPTZ;
ALTER TABLE events ADD COLUMN IF NOT EXISTS sponsor_expires_at TIMESTAMPTZ;

-- Partial index for efficient sponsored event queries
CREATE INDEX IF NOT EXISTS idx_events_sponsored
    ON events (is_sponsored, date)
    WHERE is_sponsored = true;

-- ---------------------------------------------------------------------------
-- 2. Event sponsor analytics table
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS event_sponsor_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    impressions INT DEFAULT 0,
    clicks INT DEFAULT 0,
    rsvps INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (event_id)
);

-- RLS: deny all direct access (service-only via service role key)
ALTER TABLE event_sponsor_analytics ENABLE ROW LEVEL SECURITY;
-- No policies = deny all for anon/authenticated roles

-- ---------------------------------------------------------------------------
-- 3. Update the events view to include sponsor columns
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW v_events_with_attendees_v1 AS
SELECT
    e.*,
    COALESCE(a.attendee_count, 0) AS attendee_count
FROM events e
LEFT JOIN (
    SELECT event_id, COUNT(*) AS attendee_count
    FROM event_attendees
    WHERE status IN ('going', 'interested')
    GROUP BY event_id
) a ON a.event_id = e.id;
