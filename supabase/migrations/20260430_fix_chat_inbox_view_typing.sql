-- v_chat_inbox_v1 reads from `dm_threads` (the empty legacy table).
-- The active DM-acceptance flow creates rows in chat_threads_v1, so
-- the inbox view always returned 0 rows. Replace the participants CTE
-- to read from chat_threads_v1 (kind='dm', dm_user_a/dm_user_b).

-- DROP + CREATE because column order changed (CREATE OR REPLACE
-- only works when column names+types+order match exactly).
DROP VIEW IF EXISTS public.v_chat_inbox_v1;
CREATE VIEW public.v_chat_inbox_v1 AS
WITH participants AS (
  SELECT t.id AS thread_id,
         t.dm_user_a AS user_id,
         t.dm_user_b AS other_user_id,
         'accepted'::text AS status,
         t.created_at,
         t.updated_at
  FROM public.chat_threads_v1 t
  WHERE t.kind = 'dm' AND t.dm_user_a IS NOT NULL AND t.dm_user_b IS NOT NULL
  UNION ALL
  SELECT t.id AS thread_id,
         t.dm_user_b AS user_id,
         t.dm_user_a AS other_user_id,
         'accepted'::text AS status,
         t.created_at,
         t.updated_at
  FROM public.chat_threads_v1 t
  WHERE t.kind = 'dm' AND t.dm_user_a IS NOT NULL AND t.dm_user_b IS NOT NULL
),
last_msg AS (
  SELECT DISTINCT ON (m.thread_id)
         m.thread_id,
         m.created_at AS last_message_at,
         CASE WHEN m.deleted_at IS NULL THEN m.body ELSE NULL::text END AS last_message_body
  FROM public.chat_messages_v1 m
  ORDER BY m.thread_id, m.created_at DESC
),
unread AS (
  SELECT p_1.thread_id, p_1.user_id,
         count(*) FILTER (
           WHERE m.user_id <> p_1.user_id
             AND m.deleted_at IS NULL
             AND m.created_at > COALESCE(r.last_read_at, '1970-01-01 00:00:00+00'::timestamptz)
         ) AS unread_count
  FROM participants p_1
  LEFT JOIN public.chat_messages_v1 m ON m.thread_id = p_1.thread_id
  LEFT JOIN public.chat_thread_reads_v1 r ON r.thread_id = p_1.thread_id AND r.user_id = p_1.user_id
  GROUP BY p_1.thread_id, p_1.user_id
)
SELECT p.thread_id, p.user_id, p.other_user_id, p.created_at, p.updated_at,
       NULL::text AS other_avatar_url, NULL::text AS other_display_name,
       lm.last_message_at, lm.last_message_body,
       COALESCE(u.unread_count, 0) AS unread_count
FROM participants p
LEFT JOIN last_msg lm ON lm.thread_id = p.thread_id
LEFT JOIN unread u ON u.thread_id = p.thread_id AND u.user_id = p.user_id;

-- rpc_clear_typing_v1 body deletes from `chat_typing` (no _v1 suffix);
-- that table doesn't exist. The real table is chat_typing_v1.
CREATE OR REPLACE FUNCTION public.rpc_clear_typing_v1(p_thread_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public', 'pg_temp'
AS $function$
BEGIN
  DELETE FROM public.chat_typing_v1
  WHERE thread_id = p_thread_id
    AND user_id = auth.uid();
END;
$function$;
