-- 2026-07-25: (re)create rpc_list_personalized_events_v1.
--
-- events_core.py:199 calls this RPC for every authenticated /events request.
-- It did not exist in prod, so Postgres raised
--   function rpc_list_personalized_events_v1(unknown, unknown, unknown) does not exist
-- 8 times a day. The call site catches it and falls back to
-- fetch_events_basic(), so events still listed — but EVERY authenticated user
-- silently got the generic ordering instead of the personalized one, and the
-- error churned in the Postgres log.
--
-- Deliberately NOT the version in 20260219_quick_wins.sql / 20260206_events_*.
-- Those declare a 25-column shape that no longer matches the caller, and two of
-- their types are wrong against today's schema:
--   * they return `time text`, but events.time is `time without time zone`
--   * they omit going_count / interested_count / max_attendees / is_sponsored /
--     sponsor_name / sponsor_logo_url / sponsor_expires_at, all of which the
--     caller selects
--   * attendee_count / going_count / interested_count are NOT columns on
--     `events` at all
-- Applying them verbatim would have swapped "function does not exist" for
-- "column does not exist". This definition mirrors fetch_events_basic()
-- (events_helpers.py:257) exactly — same 27 columns, same order, counts
-- COALESCEd to 0 because the accurate per-event counts come from
-- GET /events/{id}. It also reproduces that function's `status = 'published'`
-- filter, which the old migrations omitted.
--
-- Personalization = events in categories the user follows sort first, then
-- sponsored, then soonest. LIMIT/OFFSET stay with the caller.

CREATE OR REPLACE FUNCTION public.rpc_list_personalized_events_v1(
  p_user_id      text    DEFAULT NULL,
  p_category_id  text    DEFAULT NULL,
  p_include_past boolean DEFAULT false
)
RETURNS TABLE (
  id                 uuid,
  title              text,
  kind               text,
  category_id        text,
  "date"             date,
  "time"             time without time zone,
  end_date           date,
  location           text,
  online_url         text,
  image_url          text,
  description        text,
  format             text,
  status             text,
  is_public          boolean,
  latitude           double precision,
  longitude          double precision,
  created_by         uuid,
  source             text,
  attendee_count     integer,
  going_count        integer,
  interested_count   integer,
  max_attendees      integer,
  created_at         timestamptz,
  is_sponsored       boolean,
  sponsor_name       text,
  sponsor_logo_url   text,
  sponsor_expires_at timestamptz
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $fn$
  SELECT
    e.id, e.title, e.kind, e.category_id,
    e.date, e.time, e.end_date,
    e.location, e.online_url, e.image_url, e.description,
    e.format, e.status, e.is_public,
    e.latitude, e.longitude,
    e.created_by, e.source,
    0::integer AS attendee_count,
    0::integer AS going_count,
    0::integer AS interested_count,
    e.max_attendees, e.created_at,
    e.is_sponsored, e.sponsor_name, e.sponsor_logo_url, e.sponsor_expires_at
  FROM public.events e
  WHERE e.status = 'published'
    AND (p_category_id IS NULL OR e.category_id = p_category_id)
    AND (p_include_past OR e.date >= CURRENT_DATE)
  ORDER BY
    (
      p_user_id IS NOT NULL
      AND EXISTS (
        SELECT 1 FROM public.user_category_follows f
        WHERE f.user_id = NULLIF(p_user_id, '')::uuid
          AND f.category_id = e.category_id
      )
    ) DESC,
    COALESCE(e.is_sponsored, false) DESC,
    e.date ASC,
    e.id ASC;
$fn$;

GRANT EXECUTE ON FUNCTION public.rpc_list_personalized_events_v1(text, text, boolean)
  TO authenticated, service_role;
