-- 2026-09-23: chat never updated live — the realtime publication was EMPTY.
--
-- app/inbox.tsx and app/chat/[threadId].tsx subscribe to `postgres_changes`,
-- but `supabase_realtime` published no tables at all, and both screens listened
-- on `dm_messages` — a table that no longer exists (messages have lived in
-- chat_messages_v1 since the v1 chat rebuild). So nothing ever fired: a new
-- message appeared only after leaving and re-entering the screen. Walked on
-- Android 2026-09-23 with a second account: the inbox row said "No messages
-- yet" under an "Inbox, 1 unread" badge.
--
-- Realtime enforces RLS for postgres_changes, so a member only receives rows
-- chat_messages_v1_select_member lets them SELECT (threads they belong to).
-- anon holds SELECT on the table but no policy admits it (auth.uid() is null).
--
-- FALSIFIER:
--   SELECT tablename FROM pg_publication_tables
--    WHERE pubname = 'supabase_realtime';        -- expect chat_messages_v1
--   Then, with a thread open on a device, POST a message as the other member:
--   it must appear without leaving the screen.

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
     WHERE pubname = 'supabase_realtime'
       AND schemaname = 'public' AND tablename = 'chat_messages_v1'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.chat_messages_v1;
  END IF;
END $$;
