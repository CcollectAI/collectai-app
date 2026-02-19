-- Quick Wins migration: exclude_keywords for mandates + event status lifecycle
-- Items 1 & 5 from improvement roadmap

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- Item 1: Add exclude_keywords to purchase_mandates
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.purchase_mandates
  ADD COLUMN IF NOT EXISTS exclude_keywords text[] DEFAULT '{}';

COMMENT ON COLUMN public.purchase_mandates.exclude_keywords
  IS 'Keywords that disqualify a listing title from matching this mandate';

-- ─────────────────────────────────────────────────────────────────────────────
-- Item 5: Add status lifecycle to events (draft/published/cancelled)
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.events
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'published'
  CHECK (status IN ('draft', 'published', 'cancelled'));

CREATE INDEX IF NOT EXISTS idx_events_status
  ON public.events(status) WHERE status = 'published';

COMMENT ON COLUMN public.events.status
  IS 'Event lifecycle status: draft (hidden), published (visible), cancelled';

-- Update the view to include status + all enhancement columns
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
  e.status,
  coalesce(ac.attendee_count, 0)::int AS attendee_count
FROM public.events e
LEFT JOIN LATERAL (
  SELECT count(*) AS attendee_count
  FROM public.event_attendees ea
  WHERE ea.event_id = e.id
    AND ea.status IN ('going','interested')
) ac ON true;

-- Update personalized events RPC to include status
CREATE OR REPLACE FUNCTION public.rpc_list_personalized_events_v1(
  p_user_id text DEFAULT NULL,
  p_category_id text DEFAULT NULL,
  p_include_past boolean DEFAULT false
)
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
  status          text,
  attendee_count  int,
  is_attending    boolean,
  my_rsvp_status  text
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id uuid;
BEGIN
  -- Support both auth.uid() and explicit user_id parameter
  IF p_user_id IS NOT NULL THEN
    v_user_id := p_user_id::uuid;
  ELSE
    v_user_id := auth.uid();
  END IF;

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
    e.status,
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
    AND (e.is_public = true OR e.created_by = v_user_id)
    AND (e.status = 'published' OR e.created_by = v_user_id)
    AND (p_include_past = true OR e.date >= CURRENT_DATE)
    AND (p_category_id IS NULL OR e.category_id = p_category_id)
  ORDER BY e.date ASC;
END;
$$;

GRANT EXECUTE ON FUNCTION public.rpc_list_personalized_events_v1(text, text, boolean) TO authenticated;

COMMIT;
