-- 2026-07-27: wire the event display gate + rescore existing rows.
--
-- Apply with:
--   psql "$DB_DSN_DIRECT" -f 20260727c_events_display_gate_and_rescore.sql
--
-- ⚠ Apply BEFORE deploying the matching server/ change is NOT required
-- here (unlike 20260727b): this migration only adds a WHERE clause and
-- rewrites data. Old code against the new function still works — it
-- selects the same 28 columns. New code against the old function also
-- works; it just shows the junk rows until this runs. Either order is
-- safe, but the feed is only clean once BOTH have landed.
--
-- ⚠ DDL — regenerate scripts/schema.lock.json afterwards
-- (scripts/regen_schema_lock.py) or the next bake restart hard-downs the
-- API. Note this replaces a FUNCTION, and the lock tracks tables /
-- columns / uniques / checks, not functions — verified 2026-07-27 that
-- an identical function replacement left preflight_schema_lock PASSing.
-- Re-run the gate rather than trusting that note.
--
-- WHY
-- ---
-- `events.quality_score` and `events.trust_tier` have been stamped at
-- ingest since 2026-04-21 and read by NOTHING: no filter, no sort, no
-- API field, and zero references anywhere in the mobile app. The entire
-- Phase-1 scoring system in docs/EVENT_QUALITY_PLAN.md was inert.
--
-- The visible cost, found 2026-07-27 in the live Events tab: a row
-- titled
--     [Nike Vaporposite Pro](https://sneakernews.com/2025/09/01/...)
-- with location `es/#main-content)` and a description that is a copy of
-- the title. It scored 75 — "normal display" — because every rule in
-- score_event() asks a STRUCTURAL question that page chrome answers
-- correctly. All 14 `source='newsletter'` rows are boilerplate of this
-- kind ("Site Navigation", "We use Cookies", "Visit Usseguici sui
-- social"), and 9 of them were in the upcoming feed.
--
-- Root cause of the junk itself is the free-text extractor
-- (pipelines/newsletter_scraper.py::EventbriteParser._EVENT_BLOCK_RE),
-- whose title group is `[^<]{5,80}` — "any 5-80 characters that happen
-- to precede a date". That rewrite is a SEPARATE change; this migration
-- stops the output reaching users in the meantime.
--
-- WHAT THIS DOES
-- --------------
--  1. Rescores every row with the hardened scorer's penalties, so the
--     stored score finally reflects the content. Implemented in SQL that
--     mirrors app/lib/event_quality.py::score_event penalties — the
--     Python remains the source of truth for NEW rows.
--  2. Adds the display gate to rpc_list_personalized_events_v1, matching
--     events_helpers.display_gate_sql() and event_quality.is_display_ready().

BEGIN;

-- ---------------------------------------------------------------------
-- 1. Rescore. Penalties only — the positive rules already ran at ingest
--    and their inputs have not changed, so re-deriving the full score in
--    SQL would risk drifting from the Python. We subtract exactly what
--    the new penalties would have subtracted.
-- ---------------------------------------------------------------------
UPDATE events SET quality_score = GREATEST(0, LEAST(100,
      quality_score
    -- markup_in_title / markup_in_location: "](", "http://", "www."
    - CASE WHEN title    ~* '\]\(|https?://|www\.' THEN 40 ELSE 0 END
    - CASE WHEN location ~* '\]\(|https?://|www\.' THEN 40 ELSE 0 END
    -- location_not_place_shaped: populated, no comma, not a known
    -- venueless-but-valid value. Empty/NULL location is NOT penalised —
    -- 1453 limitless_tcg tournaments are online and legitimately have none.
    - CASE
        WHEN btrim(coalesce(location, '')) <> ''
         AND position(',' in location) = 0
         AND lower(btrim(location)) NOT IN
             ('online','virtual','worldwide','tba','tbd','tbc','remote','livestream')
        THEN 40 ELSE 0
      END
    -- description_is_title
    - CASE WHEN btrim(coalesce(description,'')) <> ''
            AND btrim(description) = btrim(title)
           THEN 20 ELSE 0 END
))
WHERE quality_score IS NOT NULL;

-- ---------------------------------------------------------------------
-- 2. Display gate on the personalized RPC.
--
-- Same join-key detection as 20260727b — event_attendees.event_id may be
-- text or uuid depending on whether the FK migration has run. Keeping
-- the detection means this file is order-independent too.
-- ---------------------------------------------------------------------
DO $do$
DECLARE
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

    -- Return type is unchanged (28 cols), so CREATE OR REPLACE would do;
    -- DROP+CREATE is used only to keep this file textually parallel to
    -- 20260727b, which had to drop.
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
    SELECT
      count(*) FILTER (WHERE ea.status = 'going')      AS going_count,
      count(*) FILTER (WHERE ea.status = 'interested') AS interested_count
    FROM public.event_attendees ea
    WHERE ea.event_id = %1$s
  ) ac ON true
  WHERE e.status = 'published'
    AND (p_category_id IS NULL OR e.category_id = p_category_id)
    AND (p_include_past OR e.date >= CURRENT_DATE)
    -- DISPLAY GATE. Mirrors events_helpers.display_gate_sql() and
    -- event_quality.is_display_ready(). NULL score passes: pre-backfill
    -- rows have none and failing them closed would empty the feed.
    AND (e.quality_score IS NULL OR e.quality_score >= 40)
    AND (e.source IS NULL OR e.source NOT IN ('newsletter'))
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

COMMIT;

-- Post-apply checks:
--   -- must return 0 rows:
--   SELECT id, title FROM rpc_list_personalized_events_v1(NULL, NULL, true)
--    WHERE source = 'newsletter' OR quality_score < 40;
--   -- must still return the real feed:
--   SELECT count(*) FROM rpc_list_personalized_events_v1(NULL, NULL, false);
