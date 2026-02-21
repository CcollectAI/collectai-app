-- ============================================================================
-- Migration: 20260222_events_improvements.sql
-- Purpose:   Events lifecycle improvements: templates, sponsor companies,
--            announcements, max_attendees, RSVP counts view.
-- Depends:   20260219_sponsored_events.sql
-- Safe:      Uses IF NOT EXISTS / CREATE OR REPLACE throughout.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1a. Events table additions
-- ============================================================================

ALTER TABLE events ADD COLUMN IF NOT EXISTS max_attendees INT DEFAULT NULL;
ALTER TABLE events ADD COLUMN IF NOT EXISTS sponsor_company_id uuid;

-- FK for sponsor_company_id added after sponsor_companies table is created (see below).

-- ============================================================================
-- 1b. Event templates table
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.event_templates (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid        NOT NULL REFERENCES auth.users(id),
  name          text        NOT NULL,
  template_data jsonb       NOT NULL,
  use_count     int         DEFAULT 0,
  created_at    timestamptz DEFAULT now()
);

ALTER TABLE public.event_templates ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'event_templates' AND policyname = 'event_templates_select_own'
  ) THEN
    CREATE POLICY event_templates_select_own ON public.event_templates
      FOR SELECT USING (auth.uid() = user_id);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'event_templates' AND policyname = 'event_templates_insert_own'
  ) THEN
    CREATE POLICY event_templates_insert_own ON public.event_templates
      FOR INSERT WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'event_templates' AND policyname = 'event_templates_update_own'
  ) THEN
    CREATE POLICY event_templates_update_own ON public.event_templates
      FOR UPDATE USING (auth.uid() = user_id);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'event_templates' AND policyname = 'event_templates_delete_own'
  ) THEN
    CREATE POLICY event_templates_delete_own ON public.event_templates
      FOR DELETE USING (auth.uid() = user_id);
  END IF;
END $$;

-- ============================================================================
-- 1c. Sponsor companies table
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.sponsor_companies (
  id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  name              text        NOT NULL,
  logo_url          text,
  website_url       text,
  contact_email     text        NOT NULL,
  description       text,
  stripe_customer_id text,
  admin_user_id     uuid        NOT NULL REFERENCES auth.users(id),
  is_verified       boolean     DEFAULT false,
  created_at        timestamptz DEFAULT now(),
  updated_at        timestamptz DEFAULT now()
);

ALTER TABLE public.sponsor_companies ENABLE ROW LEVEL SECURITY;

-- Everyone can see sponsor companies (logos appear on events)
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'sponsor_companies' AND policyname = 'sponsor_companies_select_all'
  ) THEN
    CREATE POLICY sponsor_companies_select_all ON public.sponsor_companies
      FOR SELECT USING (true);
  END IF;
END $$;

-- Only admin can insert
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'sponsor_companies' AND policyname = 'sponsor_companies_insert_admin'
  ) THEN
    CREATE POLICY sponsor_companies_insert_admin ON public.sponsor_companies
      FOR INSERT WITH CHECK (auth.uid() = admin_user_id);
  END IF;
END $$;

-- Only admin can update
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'sponsor_companies' AND policyname = 'sponsor_companies_update_admin'
  ) THEN
    CREATE POLICY sponsor_companies_update_admin ON public.sponsor_companies
      FOR UPDATE USING (auth.uid() = admin_user_id);
  END IF;
END $$;

-- Only admin can delete
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'sponsor_companies' AND policyname = 'sponsor_companies_delete_admin'
  ) THEN
    CREATE POLICY sponsor_companies_delete_admin ON public.sponsor_companies
      FOR DELETE USING (auth.uid() = admin_user_id);
  END IF;
END $$;

-- Now add the FK from events.sponsor_company_id -> sponsor_companies.id
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_name = 'events_sponsor_company_id_fkey'
      AND table_name = 'events'
  ) THEN
    ALTER TABLE events
      ADD CONSTRAINT events_sponsor_company_id_fkey
      FOREIGN KEY (sponsor_company_id) REFERENCES sponsor_companies(id);
  END IF;
END $$;

-- ============================================================================
-- 1d. Event announcements table (one-way broadcast)
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.event_announcements (
  id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id       uuid        NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  author_user_id uuid        NOT NULL REFERENCES auth.users(id),
  title          text,
  body           text        NOT NULL,
  image_url      text,
  created_at     timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_event_announcements_event
  ON public.event_announcements(event_id, created_at DESC);

ALTER TABLE public.event_announcements ENABLE ROW LEVEL SECURITY;

-- Attendees (going/interested) + author can read announcements
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'event_announcements' AND policyname = 'event_announcements_select_attendee'
  ) THEN
    CREATE POLICY event_announcements_select_attendee ON public.event_announcements
      FOR SELECT USING (
        auth.uid() = author_user_id
        OR EXISTS (
          SELECT 1 FROM event_attendees ea
          WHERE ea.event_id = event_announcements.event_id
            AND ea.user_id = auth.uid()
            AND ea.status IN ('going', 'interested')
        )
      );
  END IF;
END $$;

-- Only event creator or sponsor company admin can insert
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'event_announcements' AND policyname = 'event_announcements_insert_host'
  ) THEN
    CREATE POLICY event_announcements_insert_host ON public.event_announcements
      FOR INSERT WITH CHECK (
        auth.uid() = author_user_id
        AND (
          EXISTS (
            SELECT 1 FROM events e
            WHERE e.id = event_announcements.event_id
              AND e.created_by = auth.uid()
          )
          OR EXISTS (
            SELECT 1 FROM events e
            JOIN sponsor_companies sc ON sc.id = e.sponsor_company_id
            WHERE e.id = event_announcements.event_id
              AND sc.admin_user_id = auth.uid()
          )
        )
      );
  END IF;
END $$;

-- ============================================================================
-- 1e. Announcement read tracking
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.event_announcement_reads (
  announcement_id uuid        NOT NULL REFERENCES event_announcements(id) ON DELETE CASCADE,
  user_id         uuid        NOT NULL REFERENCES auth.users(id),
  read_at         timestamptz DEFAULT now(),
  PRIMARY KEY (announcement_id, user_id)
);

ALTER TABLE public.event_announcement_reads ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'event_announcement_reads' AND policyname = 'event_announcement_reads_select_own'
  ) THEN
    CREATE POLICY event_announcement_reads_select_own ON public.event_announcement_reads
      FOR SELECT USING (auth.uid() = user_id);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'event_announcement_reads' AND policyname = 'event_announcement_reads_insert_own'
  ) THEN
    CREATE POLICY event_announcement_reads_insert_own ON public.event_announcement_reads
      FOR INSERT WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

-- ============================================================================
-- 1f. RPC functions
-- ============================================================================

-- Post announcement (host or sponsor admin only)
CREATE OR REPLACE FUNCTION public.rpc_post_event_announcement_v1(
  p_event_id   uuid,
  p_title      text DEFAULT NULL,
  p_body       text DEFAULT NULL,
  p_image_url  text DEFAULT NULL
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id uuid := auth.uid();
  v_ann_id  uuid;
  v_is_host boolean;
BEGIN
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  IF p_body IS NULL OR length(trim(p_body)) = 0 THEN
    RAISE EXCEPTION 'Announcement body is required';
  END IF;

  -- Check if caller is event creator or sponsor company admin
  SELECT EXISTS (
    SELECT 1 FROM events e WHERE e.id = p_event_id AND e.created_by = v_user_id
    UNION ALL
    SELECT 1 FROM events e
    JOIN sponsor_companies sc ON sc.id = e.sponsor_company_id
    WHERE e.id = p_event_id AND sc.admin_user_id = v_user_id
  ) INTO v_is_host;

  IF NOT v_is_host THEN
    RAISE EXCEPTION 'Only event host or sponsor admin can post announcements';
  END IF;

  INSERT INTO event_announcements (event_id, author_user_id, title, body, image_url)
  VALUES (p_event_id, v_user_id, p_title, p_body, p_image_url)
  RETURNING id INTO v_ann_id;

  RETURN v_ann_id;
END;
$$;

-- Mark announcement as read
CREATE OR REPLACE FUNCTION public.rpc_mark_announcement_read_v1(
  p_announcement_id uuid
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id uuid := auth.uid();
BEGIN
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  INSERT INTO event_announcement_reads (announcement_id, user_id)
  VALUES (p_announcement_id, v_user_id)
  ON CONFLICT (announcement_id, user_id) DO NOTHING;
END;
$$;

-- ============================================================================
-- 1g. RSVP counts view
-- ============================================================================

CREATE OR REPLACE VIEW public.v_event_rsvp_counts_v1 AS
SELECT
  e.id,
  e.max_attendees,
  COUNT(*) FILTER (WHERE ea.status = 'going') AS going_count,
  COUNT(*) FILTER (WHERE ea.status = 'interested') AS interested_count,
  (e.max_attendees IS NOT NULL
   AND COUNT(*) FILTER (WHERE ea.status = 'going') >= e.max_attendees) AS is_full
FROM events e
LEFT JOIN event_attendees ea ON ea.event_id = e.id
GROUP BY e.id;

-- ============================================================================
-- Update v_events_with_attendees_v1 view to include new fields
-- ============================================================================

CREATE OR REPLACE VIEW public.v_events_with_attendees_v1 AS
SELECT
  e.*,
  COALESCE(ac.going_count, 0)::int AS going_count,
  COALESCE(ac.interested_count, 0)::int AS interested_count,
  COALESCE(ac.going_count, 0)::int + COALESCE(ac.interested_count, 0)::int AS attendee_count,
  (e.max_attendees IS NOT NULL
   AND COALESCE(ac.going_count, 0) >= e.max_attendees) AS is_full
FROM events e
LEFT JOIN (
  SELECT
    event_id,
    COUNT(*) FILTER (WHERE status = 'going') AS going_count,
    COUNT(*) FILTER (WHERE status = 'interested') AS interested_count
  FROM event_attendees
  GROUP BY event_id
) ac ON ac.event_id = e.id;

-- ============================================================================
-- GRANT EXECUTE on new RPC functions
-- ============================================================================

GRANT EXECUTE ON FUNCTION public.rpc_post_event_announcement_v1(uuid, text, text, text) TO authenticated;
GRANT EXECUTE ON FUNCTION public.rpc_mark_announcement_read_v1(uuid) TO authenticated;

COMMIT;
