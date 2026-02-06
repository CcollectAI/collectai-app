-- ============================================================================
-- Migration: 20260206_events_enhance.sql
-- Purpose:   Add format, is_public, latitude, longitude columns to events.
--            Update RPC functions and view to support the new columns.
-- Depends:   20260206_events_system.sql
-- Safe:      Uses ALTER TABLE IF patterns, CREATE OR REPLACE throughout.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. ADD NEW COLUMNS TO events
-- ============================================================================

-- format: in_person | online | hybrid
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'events'
      AND column_name  = 'format'
  ) THEN
    ALTER TABLE public.events
      ADD COLUMN format text NOT NULL DEFAULT 'in_person'
      CHECK (format IN ('in_person', 'online', 'hybrid'));
  END IF;
END $$;

-- is_public: whether the event is visible to all users
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'events'
      AND column_name  = 'is_public'
  ) THEN
    ALTER TABLE public.events
      ADD COLUMN is_public boolean NOT NULL DEFAULT true;
  END IF;
END $$;

-- latitude: geolocation for in-person / hybrid events
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'events'
      AND column_name  = 'latitude'
  ) THEN
    ALTER TABLE public.events
      ADD COLUMN latitude double precision;
  END IF;
END $$;

-- longitude: geolocation for in-person / hybrid events
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'events'
      AND column_name  = 'longitude'
  ) THEN
    ALTER TABLE public.events
      ADD COLUMN longitude double precision;
  END IF;
END $$;


-- ============================================================================
-- 2. INDEX on is_public for efficient filtering
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_events_is_public
  ON public.events(is_public);


-- ============================================================================
-- 3. UPDATE VIEW: v_events_with_attendees_v1 — include new columns
-- ============================================================================

CREATE OR REPLACE VIEW public.v_events_with_attendees_v1 AS
SELECT
  e.id,
  e.title,
  e.kind,
  e.category_id,
  e.date,
  e.time,
  e.end_date,
  e.location,
  e.online_url,
  e.description,
  e.image_url,
  e.source,
  e.source_url,
  e.created_by,
  e.created_at,
  e.updated_at,
  e.format,
  e.is_public,
  e.latitude,
  e.longitude,
  coalesce(ac.attendee_count, 0)::int AS attendee_count
FROM public.events e
LEFT JOIN LATERAL (
  SELECT count(*) AS attendee_count
  FROM public.event_attendees ea
  WHERE ea.event_id = e.id
    AND ea.status IN ('going','interested')
) ac ON true;


-- ============================================================================
-- 4. UPDATE FUNCTION: rpc_create_event_v1
--    Accept new parameters and insert them into the events table.
-- ============================================================================

CREATE OR REPLACE FUNCTION public.rpc_create_event_v1(
  p_title       text,
  p_kind        text,
  p_category_id text              DEFAULT NULL,
  p_date        date              DEFAULT NULL,
  p_time        text              DEFAULT NULL,
  p_end_date    date              DEFAULT NULL,
  p_location    text              DEFAULT NULL,
  p_online_url  text              DEFAULT NULL,
  p_description text              DEFAULT NULL,
  p_format      text              DEFAULT 'in_person',
  p_is_public   boolean           DEFAULT true,
  p_latitude    double precision  DEFAULT NULL,
  p_longitude   double precision  DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id uuid := auth.uid();
  v_id      uuid;
  v_result  jsonb;
BEGIN
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  INSERT INTO public.events (
    title, kind, category_id, date, time, end_date,
    location, online_url, description,
    format, is_public, latitude, longitude,
    source, created_by
  )
  VALUES (
    p_title, p_kind, p_category_id, p_date, p_time, p_end_date,
    p_location, p_online_url, p_description,
    p_format, p_is_public, p_latitude, p_longitude,
    'user', v_user_id
  )
  RETURNING id INTO v_id;

  SELECT jsonb_build_object(
    'id', ev.id,
    'title', ev.title,
    'kind', ev.kind,
    'category_id', ev.category_id,
    'date', ev.date,
    'time', ev.time,
    'end_date', ev.end_date,
    'location', ev.location,
    'online_url', ev.online_url,
    'description', ev.description,
    'image_url', ev.image_url,
    'source', ev.source,
    'source_url', ev.source_url,
    'created_by', ev.created_by,
    'created_at', ev.created_at,
    'updated_at', ev.updated_at,
    'format', ev.format,
    'is_public', ev.is_public,
    'latitude', ev.latitude,
    'longitude', ev.longitude
  ) INTO v_result
  FROM public.events ev
  WHERE ev.id = v_id;

  RETURN v_result;
END;
$$;


-- ============================================================================
-- 5. UPDATE FUNCTION: rpc_list_personalized_events_v1
--    Filter out is_public = false unless the user is the creator.
--    Include the new columns in the result set.
-- ============================================================================

CREATE OR REPLACE FUNCTION public.rpc_list_personalized_events_v1()
RETURNS TABLE(
  id              uuid,
  title           text,
  kind            text,
  category_id     text,
  date            date,
  time            text,
  end_date        date,
  location        text,
  online_url      text,
  description     text,
  image_url       text,
  source          text,
  source_url      text,
  created_by      uuid,
  created_at      timestamptz,
  updated_at      timestamptz,
  format          text,
  is_public       boolean,
  latitude        double precision,
  longitude       double precision,
  attendee_count  int,
  is_attending    boolean,
  my_rsvp_status  text
)
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

  RETURN QUERY
  SELECT
    e.id,
    e.title,
    e.kind,
    e.category_id,
    e.date,
    e.time,
    e.end_date,
    e.location,
    e.online_url,
    e.description,
    e.image_url,
    e.source,
    e.source_url,
    e.created_by,
    e.created_at,
    e.updated_at,
    e.format,
    e.is_public,
    e.latitude,
    e.longitude,
    coalesce(ac.cnt, 0)::int AS attendee_count,
    (my.status IS NOT NULL)  AS is_attending,
    my.status                AS my_rsvp_status
  FROM public.events e
  LEFT JOIN LATERAL (
    SELECT count(*) AS cnt
    FROM public.event_attendees ea
    WHERE ea.event_id = e.id
      AND ea.status IN ('going','interested')
  ) ac ON true
  LEFT JOIN LATERAL (
    SELECT ea2.status
    FROM public.event_attendees ea2
    WHERE ea2.event_id = e.id
      AND ea2.user_id = v_user_id
  ) my ON true
  WHERE (
      e.category_id IN (
        SELECT DISTINCT i.category
        FROM public.items i
        WHERE i.user_id = v_user_id
        UNION
        SELECT ucf.category_id
        FROM public.user_category_follows ucf
        WHERE ucf.user_id = v_user_id
      )
      OR e.category_id IS NULL
    )
    -- Only show public events, or private events created by the current user
    AND (e.is_public = true OR e.created_by = v_user_id)
  ORDER BY e.date ASC;
END;
$$;


-- ============================================================================
-- 6. GRANT EXECUTE — new function signatures
-- ============================================================================

-- rpc_create_event_v1 now has 13 parameters (added format, is_public, latitude, longitude)
GRANT EXECUTE ON FUNCTION public.rpc_create_event_v1(
  text, text, text, date, text, date, text, text, text,
  text, boolean, double precision, double precision
) TO authenticated;

-- rpc_list_personalized_events_v1 signature is unchanged (no params) but re-grant for clarity
GRANT EXECUTE ON FUNCTION public.rpc_list_personalized_events_v1() TO authenticated;


COMMIT;
