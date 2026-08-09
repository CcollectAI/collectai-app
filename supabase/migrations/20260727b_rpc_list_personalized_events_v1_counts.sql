-- 2026-07-27: rpc_list_personalized_events_v1 — real RSVP counts + the
-- caller's own RSVP status.
--
-- NOT APPLIED. Apply with:
--   psql "$DB_DSN_DIRECT" -f 20260727b_rpc_list_personalized_events_v1_counts.sql
--
-- ⚠ APPLY THIS BEFORE DEPLOYING THE MATCHING server/ CHANGE. The new
-- `user_rsvp_status` column widens the return type, so events_core.py's
-- SELECT list changes with it. If the code ships first, every authenticated
-- GET /events raises `column "user_rsvp_status" does not exist`, gets caught
-- at events_core.py:206 and silently degrades to fetch_events_basic().
--
-- ⚠ ANY DDL stales schema.lock.json — regenerate with
--   scripts/regen_schema_lock.py
-- or the next collectai-bake restart hard-downs the API.
--
-- ⚠ JOIN KEY vs 20260727_event_attendees_event_id_uuid_fk.sql. That migration
-- (server/supabase/migrations/) recasts event_attendees.event_id from text to
-- uuid, so the join key here differs depending on whether it has run —
-- `ea.event_id = e.id::text` before, `ea.event_id = e.id` after. Writing
-- either one literally leaves a migration that works in one order and
-- hard-fails in the other, so this file INSPECTS the live column type and
-- emits the matching comparison. Order does not matter.
--   Live state observed 2026-07-27 mid-session: event_id had ALREADY become
--   uuid, with event_attendees_event_id_fkey in place and the row count down
--   from 5 to 3 (the two orphans that migration deletes) — i.e. it was applied
--   to prod while this file was being written. The detection is what kept this
--   correct, so keep it even once both are in.
--
-- WHY
-- ---
-- The 2026-07-25 (re)creation of this function hardcoded
--     0::integer AS attendee_count,
--     0::integer AS going_count,
--     0::integer AS interested_count
-- and returned no RSVP-status column at all, on the reasoning that "the
-- accurate per-event counts come from GET /events/{id}". That is true for the
-- DETAIL screen and false for everything else, and the zeros are not an error
-- the caller can see — they are a plausible answer. Observed live:
--   GET /events?limit=2  ->  attendee_count: 0, going_count: 0,
--                            user_rsvp_status: null
-- while event_attendees held real rows for those events. Consequences:
--   * every event card in the list read "0 going" no matter the truth;
--   * eventsProvider derived isAttending from user_rsvp_status, so it was
--     always false — the events-tab button could add an RSVP but never show
--     or remove one, and it snapped back on the next refresh.
--
-- Both are now computed here.
--
-- PERFORMANCE
-- -----------
-- fetch_events_basic() (events_helpers.py:254) warns that
-- v_events_with_attendees_v1 "runs >30s under load", so counts must not be
-- done the view's way. They are not: the view aggregates ALL of
-- event_attendees with a bare GROUP BY and then joins the result to every
-- event. Below, the aggregate is a correlated LATERAL evaluated per candidate
-- event and driven by an index, and the RSVP-status lookup is a scalar
-- subquery the planner defers until after the caller's LIMIT.
--
-- Measured on prod by rendering this file's DDL, extracting the body and
-- running EXPLAIN (ANALYZE, BUFFERS) on it — read-only, the function itself
-- was NOT replaced. 2026-07-27, 2023 events / 142 published upcoming /
-- LIMIT 20 / p_include_past=false, i.e. the shape events_core.py actually
-- calls:
--   Planning Time 0.403 ms, Execution Time 2.289 ms
--   -> Limit -> top-N heapsort -> Nested Loop Left Join (142 rows)
--   -> LATERAL aggregate: 0.001 ms x 142 loops
--   -> user_rsvp_status SubPlan: 20 loops (post-LIMIT, not 142)
-- The same body with p_include_past=true and no LIMIT (2023 rows, not a shape
-- any caller uses) costs 322 ms, so the LIMIT is doing real work — do not
-- remove it from the call site.
--
-- Both event_attendees accesses currently plan as seq scans, correctly:
-- the table holds 3 rows and a scan is one page. event_attendees_event_idx
-- and event_attendees_event_id_user_id_key both exist and cover these exact
-- predicates, so the planner switches over on its own as the table grows. No
-- new index is added here — see DATA_SCALING_PLAN.md §index policy.

DO $do$
DECLARE
    -- 'text' before 20260727_event_attendees_event_id_uuid_fk.sql, 'uuid'
    -- after. Never cast the INDEXED side (ea.event_id) — doing so makes the
    -- column non-indexable and drops event_attendees_event_idx from the plan.
    v_key_type text;
    v_join     text;
BEGIN
    SELECT data_type INTO v_key_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'event_attendees'
      AND column_name  = 'event_id';

    IF v_key_type IS NULL THEN
        RAISE EXCEPTION 'public.event_attendees.event_id not found — refusing to guess the join key.';
    ELSIF v_key_type = 'uuid' THEN
        v_join := 'e.id';
    ELSIF v_key_type = 'text' THEN
        v_join := 'e.id::text';
    ELSE
        RAISE EXCEPTION
            'public.event_attendees.event_id is %, expected text or uuid.', v_key_type;
    END IF;

    RAISE NOTICE 'event_attendees.event_id is %; joining on ea.event_id = %', v_key_type, v_join;

    -- Return type is changing (27 -> 28 columns), and CREATE OR REPLACE cannot
    -- change a function's return type. Drop first.
    DROP FUNCTION IF EXISTS public.rpc_list_personalized_events_v1(text, text, boolean);

    EXECUTE format($fmt$
CREATE FUNCTION public.rpc_list_personalized_events_v1(
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
  sponsor_expires_at timestamptz,
  user_rsvp_status   text
)
LANGUAGE sql
STABLE
-- SECURITY DEFINER is required, not incidental: event_attendees carries a
-- single RLS policy, `event_attendees_deny_all` (FOR ALL, USING false). An
-- INVOKER-rights function would read zero attendee rows for every caller and
-- COALESCE its way back to exactly the 0/0/null this migration exists to fix.
-- The function only ever exposes AGGREGATES plus the caller OWN row
-- (user_id = p_user_id), so it does not leak the attendee list.
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
    (COALESCE(ac.going_count, 0) + COALESCE(ac.interested_count, 0))::integer AS attendee_count,
    COALESCE(ac.going_count, 0)::integer      AS going_count,
    COALESCE(ac.interested_count, 0)::integer AS interested_count,
    e.max_attendees, e.created_at,
    e.is_sponsored, e.sponsor_name, e.sponsor_logo_url, e.sponsor_expires_at,
    -- The caller own RSVP, or NULL when anonymous / not RSVP'd. Matches what
    -- GET /events/{id} resolves at events_core.py:966 so the list and the
    -- detail screen cannot disagree about the same event.
    CASE
      WHEN NULLIF(p_user_id, '') IS NULL THEN NULL
      ELSE (
        SELECT ea.status
        FROM public.event_attendees ea
        WHERE ea.event_id = %1$s
          AND ea.user_id = NULLIF(p_user_id, '')::uuid
        LIMIT 1
      )
    END AS user_rsvp_status
  FROM public.events e
  LEFT JOIN LATERAL (
    -- Same status semantics as v_events_with_attendees_v1: attendee_count is
    -- going + interested. 'not_going' counts towards neither.
    SELECT
      count(*) FILTER (WHERE ea.status = 'going')      AS going_count,
      count(*) FILTER (WHERE ea.status = 'interested') AS interested_count
    FROM public.event_attendees ea
    WHERE ea.event_id = %1$s
  ) ac ON true
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
$fmt$, v_join);
END
$do$;

GRANT EXECUTE ON FUNCTION public.rpc_list_personalized_events_v1(text, text, boolean)
  TO authenticated, service_role;

-- Post-apply check. MUST return at least one row with a non-zero count — an
-- empty result means the join key is wrong again and the zeros are back:
--   SELECT id, title, going_count, interested_count, attendee_count,
--          user_rsvp_status
--     FROM rpc_list_personalized_events_v1('<a-user-uuid>', NULL, true)
--    WHERE attendee_count > 0;
