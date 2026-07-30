-- chat_threads_v1 had no foreign keys to auth.users, so deleting a user left
-- dangling threads pointing at nobody.
--
-- Measured on prod 2026-07-31, before this migration:
--   * 7 `kind='dm'` threads — 2 with an orphaned dm_user_a, 4 with an orphaned
--     dm_user_b (5 distinct threads affected)
--   * 10 threads total — 8 with an orphaned created_by
--   * chat_messages_v1.user_id: 5 rows, 0 orphans (no FK needed today, but see
--     the note at the bottom)
--
-- Not user-visible: v_chat_inbox_v1 LEFT JOINs profiles, so an orphan rendered
-- through the 'Unknown' fallback rather than failing. It is hygiene — but any
-- future join that assumes the counterparty exists would find these.
--
-- The asymmetry that exposed it: offers.buyer_id DOES have an FK, so seeding a
-- test offer against one of these orphaned ids failed loudly with
-- offers_buyer_id_fkey. Same class of reference, opposite behaviour.
--
-- Two different delete semantics, deliberately:
--
--   dm_user_a / dm_user_b  -> ON DELETE CASCADE
--       A DM is meaningless once either party is gone, and v_chat_inbox_v1
--       already requires both to be non-null. Cascading removes the thread and
--       (via the existing chat_messages_v1_thread_id_fkey ON DELETE CASCADE)
--       its messages, members and read receipts.
--
--   created_by             -> ON DELETE SET NULL
--       CASCADE would be WRONG here: it would destroy shared `category` and
--       `private` threads whose creator happens to have left, taking every
--       other member's history with them. SET NULL keeps the thread and drops
--       only the dangling reference. Requires dropping NOT NULL, which is safe
--       because `created_by` has **zero readers** anywhere in the codebase
--       (server, providers and screens all checked) — it is write-only.
--
-- Backup of the rows deleted below:
--   /opt/collectors/logs/chat_orphan_backup_20260731.json

BEGIN;

-- 1. Remove DM threads whose counterparty no longer exists. Child rows go via
--    the existing thread_id cascades.
DELETE FROM public.chat_threads_v1 t
 WHERE t.kind = 'dm'
   AND ( (t.dm_user_a IS NOT NULL AND NOT EXISTS (SELECT 1 FROM auth.users u WHERE u.id = t.dm_user_a))
      OR (t.dm_user_b IS NOT NULL AND NOT EXISTS (SELECT 1 FROM auth.users u WHERE u.id = t.dm_user_b)) );

-- 2. Null out dangling creators so the FK can be added without dropping the
--    shared threads those rows represent.
ALTER TABLE public.chat_threads_v1 ALTER COLUMN created_by DROP NOT NULL;

UPDATE public.chat_threads_v1 t
   SET created_by = NULL
 WHERE t.created_by IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM auth.users u WHERE u.id = t.created_by);

-- 3. The constraints themselves.
ALTER TABLE public.chat_threads_v1
  DROP CONSTRAINT IF EXISTS chat_threads_v1_dm_user_a_fkey,
  DROP CONSTRAINT IF EXISTS chat_threads_v1_dm_user_b_fkey,
  DROP CONSTRAINT IF EXISTS chat_threads_v1_created_by_fkey;

ALTER TABLE public.chat_threads_v1
  ADD CONSTRAINT chat_threads_v1_dm_user_a_fkey
  FOREIGN KEY (dm_user_a) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public.chat_threads_v1
  ADD CONSTRAINT chat_threads_v1_dm_user_b_fkey
  FOREIGN KEY (dm_user_b) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public.chat_threads_v1
  ADD CONSTRAINT chat_threads_v1_created_by_fkey
  FOREIGN KEY (created_by) REFERENCES auth.users(id) ON DELETE SET NULL;

COMMIT;

-- Deliberately NOT added: chat_messages_v1.user_id -> auth.users. It has zero
-- orphans today, and the right semantics are unclear (deleting an author should
-- arguably keep a group thread readable rather than punch holes in it). Revisit
-- with a tombstone/anonymise decision rather than a bare CASCADE.
