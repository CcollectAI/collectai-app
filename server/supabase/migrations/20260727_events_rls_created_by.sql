-- events RLS: key ownership off created_by, and stop the read policy from
-- returning private events to every authenticated client.
--
-- Apply via: psql $DB_DSN_DIRECT -f 20260727_events_rls_created_by.sql
--
-- WHY
-- ---
-- Verified on prod 2026-07-27 with pg_get_expr(polqual/polwithcheck) — policy
-- NAMES are not evidence, so the bodies were read directly:
--
--   own_events           FOR ALL  USING (user_id = auth.uid())
--                                 WITH CHECK (user_id = auth.uid())
--   "events are readable" FOR SELECT USING (true)
--
-- events.user_id is NULL on all 2023 rows (SELECT count(user_id) FROM events
-- => 0). The application writes created_by, not user_id: all 5 user-created
-- rows (source='user') have created_by set, and
-- server/app/features/events/events_core.py inserts/reads created_by
-- throughout. `user_id = auth.uid()` is therefore NULL for every row, which is
-- not true, so own_events grants exactly nothing. It is a no-op policy that
-- reads like an ownership rule.
--
-- Two consequences:
--
--   1. Reads. Because own_events grants nothing, the only SELECT grant is
--      `USING (true)`. v_events_with_attendees_v1 is security_invoker=true and
--      IS read directly by the client
--      (src/data/providers/eventsProvider.ts:113, categoryProvider.ts:66), so
--      an authenticated client can read every events row through it —
--      including is_public = false. The is_public gate exists only in the
--      backend (events_core.py:962, "Hide non-public events unless the user is
--      the creator"), and the view bypasses the backend entirely. There are 0
--      private rows today, so this is latent — it becomes a live leak the
--      moment someone creates one.
--
--   2. Writes. Client-side INSERT/UPDATE/DELETE on events are all rejected,
--      silently, for the same reason. Not a regression here (event CRUD goes
--      through the EC2 backend, which connects as `postgres` — verified
--      rolbypassrls = true — so it is unaffected by every policy in this file),
--      but the policy should mean what it says.
--
-- FIX: key both policies off created_by, and make the read policy match the
-- backend's own rule. Deliberately NOT a backfill of user_id: created_by is
-- the column the code actually writes, 44 read sites included, and populating a
-- second ownership column would leave two sources of truth to drift apart.
--
-- Blast radius today: none. is_public is TRUE on all 2023 rows and NULL on
-- none, so the narrowed read policy filters zero rows right now; it only
-- starts mattering when a private event exists. `IS TRUE` (not `= true`) so a
-- future NULL fails closed.

BEGIN;

-- Ownership: created_by, the column the app writes.
DROP POLICY IF EXISTS own_events ON public.events;
CREATE POLICY own_events ON public.events
    FOR ALL
    USING (created_by = auth.uid())
    WITH CHECK (created_by = auth.uid());

-- Read: public events, plus your own drafts. Replaces `USING (true)`.
-- The old policy's name ("events are readable") described the removed
-- behaviour, so it is retired rather than rewritten in place.
DROP POLICY IF EXISTS "events are readable" ON public.events;
DROP POLICY IF EXISTS events_select_public_or_own ON public.events;
CREATE POLICY events_select_public_or_own ON public.events
    FOR SELECT
    USING (is_public IS TRUE OR created_by = auth.uid());

-- The read policy now filters on created_by on every row it cannot satisfy
-- via is_public; keep that lookup off a sequential scan.
CREATE INDEX IF NOT EXISTS idx_events_created_by ON public.events (created_by);

COMMIT;
