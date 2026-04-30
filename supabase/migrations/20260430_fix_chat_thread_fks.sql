-- Fix chat schema inconsistency: chat_messages_v1.thread_id and
-- chat_thread_reads_v1.thread_id FK to the empty legacy `dm_threads`
-- table, but the active DM-acceptance flow (rpc_decide_dm_request_v1)
-- creates rows in `chat_threads_v1`. Result: every sendMessage and
-- markThreadRead 409'd with FK violation.
--
-- chat_thread_members_v1 and chat_typing_v1 already FK to
-- chat_threads_v1 correctly. Migrate the other two to match.

ALTER TABLE public.chat_messages_v1
  DROP CONSTRAINT IF EXISTS chat_messages_v1_thread_id_fkey;
ALTER TABLE public.chat_messages_v1
  ADD CONSTRAINT chat_messages_v1_thread_id_fkey
  FOREIGN KEY (thread_id) REFERENCES public.chat_threads_v1(id) ON DELETE CASCADE;

ALTER TABLE public.chat_thread_reads_v1
  DROP CONSTRAINT IF EXISTS chat_thread_reads_v1_thread_id_fkey;
ALTER TABLE public.chat_thread_reads_v1
  ADD CONSTRAINT chat_thread_reads_v1_thread_id_fkey
  FOREIGN KEY (thread_id) REFERENCES public.chat_threads_v1(id) ON DELETE CASCADE;

-- rpc_set_typing_v1 has two overloads — the FE doesn't pass
-- p_is_typing, which makes PostgREST hit PGRST203 "Could not choose
-- the best candidate function". Drop the no-default overload (the
-- one with p_is_typing default=true is the canonical signature).
DROP FUNCTION IF EXISTS public.rpc_set_typing_v1(p_thread_id uuid);
