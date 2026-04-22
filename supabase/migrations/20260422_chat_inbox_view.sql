-- Chat inbox view + read-state FK repoint (2026-04-22)
-- Completes the chat-fix pass by giving chat_router.py the v_chat_inbox_v1
-- view it has been querying (GET /chat/threads + GET /chat/unread-count)
-- and standardizing read-state tracking on the canonical dm_threads table.
-- Mirrors Instagram/WhatsApp inbox conventions: one row per (user, thread),
-- with last-message preview, unread count, and other-participant profile.

-- ---------------------------------------------------------------------------
-- 1. Repoint chat_thread_reads_v1.thread_id FK → dm_threads(id)
-- ---------------------------------------------------------------------------
-- Same rationale as 20260422_chat_messages_repoint_dm_threads.sql: the old
-- FK pointed at chat_threads_v1, which is no longer used for DMs.

DELETE FROM public.chat_thread_reads_v1
WHERE thread_id NOT IN (SELECT id FROM public.dm_threads);

ALTER TABLE public.chat_thread_reads_v1
  DROP CONSTRAINT IF EXISTS chat_thread_reads_v1_thread_id_fkey;

ALTER TABLE public.chat_thread_reads_v1
  ADD CONSTRAINT chat_thread_reads_v1_thread_id_fkey
  FOREIGN KEY (thread_id) REFERENCES public.dm_threads(id)
  ON DELETE CASCADE;

-- ---------------------------------------------------------------------------
-- 2. v_chat_inbox_v1 — one row per (viewer, thread)
-- ---------------------------------------------------------------------------

DROP VIEW IF EXISTS public.v_chat_inbox_v1;

CREATE VIEW public.v_chat_inbox_v1 AS
WITH participants AS (
  -- Requester's perspective
  SELECT t.id            AS thread_id,
         t.requester_id  AS user_id,
         t.responder_id  AS other_user_id,
         t.status,
         t.created_at,
         t.updated_at
  FROM public.dm_threads t
  WHERE t.status = 'accepted'
  UNION ALL
  -- Responder's perspective (same thread, flipped participants)
  SELECT t.id            AS thread_id,
         t.responder_id  AS user_id,
         t.requester_id  AS other_user_id,
         t.status,
         t.created_at,
         t.updated_at
  FROM public.dm_threads t
  WHERE t.status = 'accepted'
),
last_msg AS (
  SELECT DISTINCT ON (m.thread_id)
         m.thread_id,
         m.created_at AS last_message_at,
         CASE WHEN m.deleted_at IS NULL THEN m.body END AS last_message_body
  FROM public.chat_messages_v1 m
  ORDER BY m.thread_id, m.created_at DESC
),
unread AS (
  SELECT
    p.thread_id,
    p.user_id,
    COUNT(*) FILTER (
      WHERE m.user_id <> p.user_id
        AND m.deleted_at IS NULL
        AND m.created_at > COALESCE(r.last_read_at, '1970-01-01'::timestamptz)
    ) AS unread_count
  FROM participants p
  LEFT JOIN public.chat_messages_v1 m ON m.thread_id = p.thread_id
  LEFT JOIN public.chat_thread_reads_v1 r
         ON r.thread_id = p.thread_id AND r.user_id = p.user_id
  GROUP BY p.thread_id, p.user_id
)
SELECT
  p.thread_id,
  p.user_id,
  p.other_user_id,
  pr.username                  AS other_display_name,
  NULL::text                   AS other_avatar_url,  -- profiles has no avatar column yet
  l.last_message_at,
  l.last_message_body,
  COALESCE(u.unread_count, 0)  AS unread_count,
  p.created_at,
  p.updated_at
FROM participants p
LEFT JOIN public.profiles pr ON pr.id = p.other_user_id
LEFT JOIN last_msg l         ON l.thread_id = p.thread_id
LEFT JOIN unread u           ON u.thread_id = p.thread_id AND u.user_id = p.user_id;

GRANT SELECT ON public.v_chat_inbox_v1 TO authenticated, service_role;

COMMENT ON VIEW public.v_chat_inbox_v1 IS
  'Per-user DM inbox. One row per (user_id, thread_id) for accepted dm_threads, with last-message preview + unread count (Instagram-style request-gated DMs).';
