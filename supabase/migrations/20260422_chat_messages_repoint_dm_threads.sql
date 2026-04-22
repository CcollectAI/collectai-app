-- Chat: repoint chat_messages_v1.thread_id FK to dm_threads(id).
-- 2026-04-22: the chat router uses dm_threads (with requester/responder
-- pending/accepted/declined — Instagram-style request-gated DMs) for all
-- thread lookups, but chat_messages_v1 historically FK'd to chat_threads_v1.
-- Those two tables are populated independently, which meant every message
-- insert failed FK validation. Standardizing on dm_threads so the router's
-- existing "DM-request" UX (pending → accepted → open chat) is the single
-- source of truth. chat_threads_v1 stays around for category/group chat
-- rooms (kind='category'), which use the same table but different columns.

-- 1. Clean orphan messages (any rows whose thread_id isn't in dm_threads).
--    Safe because all 8 current rows are dev/test data — verified 2026-04-22.
DELETE FROM public.chat_messages_v1
WHERE thread_id NOT IN (SELECT id FROM public.dm_threads);

-- 2. Swap the FK.
ALTER TABLE public.chat_messages_v1
  DROP CONSTRAINT IF EXISTS chat_messages_v1_thread_id_fkey;

ALTER TABLE public.chat_messages_v1
  ADD CONSTRAINT chat_messages_v1_thread_id_fkey
  FOREIGN KEY (thread_id) REFERENCES public.dm_threads(id)
  ON DELETE CASCADE;

-- 3. Make sure the FK target is indexed for fast CASCADEs + joins.
--    dm_threads(id) is the primary key, already indexed. Nothing to add.
