-- Chat: edit-within-15min + soft-delete + RPC repair
-- Written 2026-04-22 after discovering chat_router.py + rpc_send_message_v1
-- were both broken against the live chat_messages_v1 schema (5 ghost column
-- references + wrong RPC arity). See docs/EVENT_QUALITY_PLAN.md peer + the
-- chat-fix pass for full history. This migration is idempotent.

-- 1. Columns expected by the router's PATCH/DELETE/list endpoints.
ALTER TABLE public.chat_messages_v1
  ADD COLUMN IF NOT EXISTS edited_at  timestamptz,
  ADD COLUMN IF NOT EXISTS deleted_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_chat_messages_v1_deleted_at
  ON public.chat_messages_v1 (deleted_at)
  WHERE deleted_at IS NOT NULL;

-- 2. Rewrite rpc_send_message_v1 to match reality:
--    - takes (thread_id, user_id, body) to match the Python asyncpg caller
--      (chat_router.send_message passes 3 args; old signature took 2)
--    - inserts into the actual column `user_id` (old version used the
--      non-existent column `sender_user_id`)
--    - drops the auth.uid() / chat_thread_members_v1 membership check
--      because the caller (chat_router) already validates participation
--      via _get_thread_participant against dm_threads. Double-gating via
--      chat_thread_members_v1 was the old design but that table is not
--      kept in sync with dm_threads.

DROP FUNCTION IF EXISTS public.rpc_send_message_v1(uuid, text);
DROP FUNCTION IF EXISTS public.rpc_send_message_v1(uuid, uuid, text);

CREATE OR REPLACE FUNCTION public.rpc_send_message_v1(
  p_thread_id uuid,
  p_user_id   uuid,
  p_body      text
)
RETURNS public.chat_messages_v1
LANGUAGE plpgsql
SECURITY DEFINER
AS $function$
declare
  v_row public.chat_messages_v1;
begin
  if p_user_id is null then
    raise exception 'user_id required';
  end if;
  if p_body is null or length(trim(p_body)) = 0 then
    raise exception 'body required';
  end if;

  insert into public.chat_messages_v1 (thread_id, user_id, body)
  values (p_thread_id, p_user_id, p_body)
  returning * into v_row;

  return v_row;
end;
$function$;

-- Keep permissions in sync with the replaced function.
REVOKE ALL ON FUNCTION public.rpc_send_message_v1(uuid, uuid, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.rpc_send_message_v1(uuid, uuid, text) TO authenticated, service_role;
