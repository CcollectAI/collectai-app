-- v_chat_inbox_v1: make the REPO match the database.
--
-- Found 2026-09-17 by class sweep J, then verified against production before
-- being believed. The repo's 20260430_fix_chat_inbox_view_typing.sql DROPs and
-- re-CREATEs this view with:
--   * NO `WHERE p.user_id = auth.uid()`, and
--   * no `security_invoker = true` (a fresh view takes default reloptions, so
--     the three blanket ALTER VIEW ... security_invoker migrations of 20260424
--     do not apply to it).
-- A view runs as its OWNER in that state, so RLS on chat_threads_v1 /
-- chat_messages_v1 would NOT apply and every member would read every DM thread,
-- last_message_body included.
--
-- PRODUCTION WAS NEVER EXPOSED. The live view was read back on 2026-09-17 and
-- ends in `WHERE p.user_id = auth.uid()`; both base tables have RLS enabled
-- with member-scoped SELECT policies (chat_threads_v1_select_member,
-- chat_messages_v1_select_member). The fix was applied to the database and
-- never written back to the repo — so the danger was that replaying the repo
-- would UNDO it.
--
-- This file is that missing write-back: the body below is pg_get_viewdef() of
-- the live view, so applying it is a no-op against production and the repo can
-- no longer recreate the unfiltered version. It also restores the two profile
-- columns the 20260430 file had stubbed to NULL::text.
--
-- The class is gated by `npm run check:view-rls`.

DROP VIEW IF EXISTS public.v_chat_inbox_v1;
CREATE VIEW public.v_chat_inbox_v1 AS
 WITH participants AS (
         SELECT t.id AS thread_id,
            t.dm_user_a AS user_id,
            t.dm_user_b AS other_user_id,
            'accepted'::text AS status,
            t.created_at,
            t.updated_at
           FROM chat_threads_v1 t
          WHERE t.kind = 'dm'::text AND t.dm_user_a IS NOT NULL AND t.dm_user_b IS NOT NULL
        UNION ALL
         SELECT t.id,
            t.dm_user_b,
            t.dm_user_a,
            'accepted'::text AS text,
            t.created_at,
            t.updated_at
           FROM chat_threads_v1 t
          WHERE t.kind = 'dm'::text AND t.dm_user_a IS NOT NULL AND t.dm_user_b IS NOT NULL
        ), last_msg AS (
         SELECT DISTINCT ON (m.thread_id) m.thread_id,
            m.created_at AS last_message_at,
                CASE
                    WHEN m.deleted_at IS NULL THEN m.body
                    ELSE NULL::text
                END AS last_message_body
           FROM chat_messages_v1 m
          ORDER BY m.thread_id, m.created_at DESC
        ), unread AS (
         SELECT p_1.thread_id,
            p_1.user_id,
            count(*) FILTER (WHERE m.user_id <> p_1.user_id AND m.deleted_at IS NULL AND m.created_at > COALESCE(r.last_read_at, '1970-01-01 00:00:00+00'::timestamp with time zone)) AS unread_count
           FROM participants p_1
             LEFT JOIN chat_messages_v1 m ON m.thread_id = p_1.thread_id
             LEFT JOIN chat_thread_reads_v1 r ON r.thread_id = p_1.thread_id AND r.user_id = p_1.user_id
          GROUP BY p_1.thread_id, p_1.user_id
        )
 SELECT p.thread_id,
    p.user_id,
    p.other_user_id,
    p.created_at,
    p.updated_at,
    prof.avatar_url AS other_avatar_url,
    COALESCE(prof.display_name, prof.username) AS other_display_name,
    lm.last_message_at,
    lm.last_message_body,
    COALESCE(u.unread_count, 0::bigint) AS unread_count
   FROM participants p
     LEFT JOIN last_msg lm ON lm.thread_id = p.thread_id
     LEFT JOIN unread u ON u.thread_id = p.thread_id AND u.user_id = p.user_id
     LEFT JOIN profiles prof ON prof.id = p.other_user_id
  WHERE p.user_id = auth.uid();
