-- event_attendees.event_id: text with no foreign key -> uuid with a real FK.
--
-- Apply via: psql $DB_DSN_DIRECT -f 20260727_event_attendees_event_id_uuid_fk.sql
--
-- WHY
-- ---
-- event_attendees.event_id is `text`. events.id is `uuid`. There is no foreign
-- key between them (verified: pg_constraint on event_attendees holds only the
-- PK on id and the UNIQUE on (event_id, user_id) — no contype='f' at all).
-- Nothing has ever stopped an RSVP from pointing at an event that does not
-- exist, and 2 of the 5 live rows do:
--
--   240a5cbb-cd42-46ad-a79a-24b70be0ee2a  user 1095b597…  (no such event)
--   00000000-0000-0000-0000-000000000000  user 20503ad2…  (no such event —
--                                                          a nil-uuid sentinel)
--
-- This is not the schema anyone designed. supabase/migrations/20260206_events_system.sql:150
-- declares `event_id uuid NOT NULL REFERENCES public.events(id) ON DELETE
-- CASCADE`. The live table drifted off that: uuid became text and the FK never
-- existed. Every sibling table kept the original shape and still has its FK —
-- event_announcements, event_sponsor_analytics and user_drop_alerts all have
-- `event_id uuid REFERENCES events(id) ON DELETE CASCADE`, and event_tickets is
-- uuid too. event_attendees is the only one that drifted, so this restores the
-- house convention rather than inventing one.
--
-- The drift is already visible in the source as scar tissue: five call sites
-- cast around the mismatch (events_core.py:129-130 `ea.event_id::uuid = e.id`,
-- events_announcements.py:311 with a comment explaining the "legacy schema
-- mismatch", sponsor_company_router.py:628, and intelligence_router.py:355 /
-- event_engagement_worker.py:122 casting the other way with `event_id::text`).
--
-- WHY CAST TO uuid RATHER THAN VALIDATE THE text SOME OTHER WAY
-- -------------------------------------------------------------
-- A CHECK constraint or a trigger could enforce referential integrity across
-- the type boundary, but both are strictly worse: they duplicate what an FK
-- does natively, they do not cascade on event deletion, and they leave the
-- planner comparing text to uuid forever. The cast is safe here, and each
-- premise was verified on prod rather than assumed:
--
--   1. Every live value is already uuid-shaped. A regex over all 5 rows
--      returned 0 non-conforming values; after the 2 orphans are deleted, the
--      3 survivors are uuids that exist in events.
--   2. Every writer already produces a uuid. events_rsvp.py validates with
--      `UUID(event_id)` and raises 400 before the INSERT on both the RSVP and
--      un-RSVP paths; billing_router.py:960 inserts inside a transaction that
--      has already written the same event_id into event_tickets.event_id,
--      which is a uuid column, so a malformed value fails upstream.
--   3. The driver handles it. Verified against asyncpg on EC2: a Python str
--      binds cleanly to a uuid parameter, and a malformed str is rejected with
--      DataError at the driver. That is strictly better than today, where a
--      junk string is accepted and stored.
--   4. The existing casts stay valid. `event_id::uuid` becomes uuid::uuid and
--      `event_id::text` becomes uuid::text; both still compile, so no
--      application code has to change and nothing needs redeploying.
--   5. Exactly one database object depends on the column — the view below
--      (pg_depend via pg_rewrite). No functions reference event_attendees
--      (pg_proc.prosrc scan: 0 hits) and the table has no triggers.
--
-- The view has to be dropped and recreated because its join is
-- `ac.event_id = e.id::text`; once event_id is uuid that comparison is
-- uuid = text, which has no operator. Postgres would refuse the ALTER anyway.
-- Both happen in one transaction, so the view is never observably missing, and
-- its grants and the security_invoker setting are restored explicitly — DROP
-- VIEW discards both.

BEGIN;

-- ---------------------------------------------------------------------------
-- Preconditions. Refuse to run if prod does not look the way it was surveyed.
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    n_bad_shape  int;
    n_orphan     int;
BEGIN
    SELECT count(*) INTO n_bad_shape
    FROM public.event_attendees
    WHERE event_id !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';
    IF n_bad_shape > 0 THEN
        RAISE EXCEPTION
            'event_attendees holds % non-uuid event_id value(s); the cast would fail. Inspect before rerunning.',
            n_bad_shape;
    END IF;

    SELECT count(*) INTO n_orphan
    FROM public.event_attendees a
    WHERE NOT EXISTS (SELECT 1 FROM public.events e WHERE e.id::text = a.event_id);
    IF n_orphan <> 2 THEN
        RAISE EXCEPTION
            'expected exactly 2 orphaned event_attendees rows, found %. Re-verify before deleting.',
            n_orphan;
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 1. Remove the orphans. They cannot be repaired: the events they point at do
--    not exist and never will, so an FK has nothing to attach them to.
-- ---------------------------------------------------------------------------
DELETE FROM public.event_attendees a
WHERE NOT EXISTS (SELECT 1 FROM public.events e WHERE e.id::text = a.event_id);

-- ---------------------------------------------------------------------------
-- 2. Drop the only dependent object so the column type can change.
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS public.v_events_with_attendees_v1;

-- ---------------------------------------------------------------------------
-- 3. text -> uuid. Rebuilds event_attendees_event_id_user_id_key and
--    event_attendees_event_idx automatically.
-- ---------------------------------------------------------------------------
ALTER TABLE public.event_attendees
    ALTER COLUMN event_id TYPE uuid USING event_id::uuid;

-- ---------------------------------------------------------------------------
-- 4. The foreign key the 20260206 migration always intended. ON DELETE CASCADE
--    matches events' three other children.
-- ---------------------------------------------------------------------------
ALTER TABLE public.event_attendees
    ADD CONSTRAINT event_attendees_event_id_fkey
    FOREIGN KEY (event_id) REFERENCES public.events(id) ON DELETE CASCADE;

-- ---------------------------------------------------------------------------
-- 5. Recreate the view. Identical to the captured definition except the join,
--    which loses its now-invalid ::text cast.
-- ---------------------------------------------------------------------------
CREATE VIEW public.v_events_with_attendees_v1 AS
SELECT
    e.id, e.user_id, e.item_id, e.kind, e.payload, e.created_at, e.category,
    e.canonical_key, e.event_type, e.starts_at, e.ends_at, e.title,
    e.description, e.source, e.url, e.is_sponsored, e.sponsor_name,
    e.sponsor_logo_url, e.sponsor_tier, e.sponsor_paid_at, e.sponsor_expires_at,
    e.category_id, e.date, e."time", e.end_date, e.location, e.online_url,
    e.image_url, e.source_url, e.format, e.status, e.is_public, e.max_attendees,
    e.latitude, e.longitude, e.visibility, e.created_by, e.updated_at,
    COALESCE(ac.going_count, 0::bigint)::integer      AS going_count,
    COALESCE(ac.interested_count, 0::bigint)::integer AS interested_count,
    COALESCE(ac.going_count, 0::bigint)::integer
        + COALESCE(ac.interested_count, 0::bigint)::integer AS attendee_count,
    e.max_attendees IS NOT NULL
        AND COALESCE(ac.going_count, 0::bigint) >= e.max_attendees AS is_full
FROM public.events e
LEFT JOIN (
    SELECT event_attendees.event_id,
           count(*) FILTER (WHERE event_attendees.status = 'going'::text)      AS going_count,
           count(*) FILTER (WHERE event_attendees.status = 'interested'::text) AS interested_count
    FROM public.event_attendees
    GROUP BY event_attendees.event_id
) ac ON ac.event_id = e.id;

-- DROP VIEW discarded these; restore exactly what was captured beforehand.
ALTER VIEW public.v_events_with_attendees_v1 SET (security_invoker = true);
GRANT ALL ON public.v_events_with_attendees_v1 TO anon, authenticated, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.v_events_with_attendees_v1 TO collector_bot;

COMMIT;
