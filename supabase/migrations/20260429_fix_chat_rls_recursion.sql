-- Fix infinite recursion on chat_thread_members_v1 RLS policy.
-- Root cause: the SELECT policy referenced chat_thread_members_v1 in its
-- USING clause, which re-triggered the same policy → 42P17 every time
-- the FE hit the inbox view, messages, typing, or reactions.

CREATE OR REPLACE FUNCTION public.is_chat_thread_member(p_thread_id uuid, p_user_id uuid)
RETURNS boolean
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, pg_temp
STABLE
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.chat_thread_members_v1
    WHERE thread_id = p_thread_id AND user_id = p_user_id
  );
$$;

REVOKE ALL ON FUNCTION public.is_chat_thread_member(uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.is_chat_thread_member(uuid, uuid) TO authenticated, anon, service_role;

DROP POLICY IF EXISTS chat_thread_members_v1_select_same_thread ON public.chat_thread_members_v1;

CREATE POLICY chat_thread_members_v1_select_same_thread
  ON public.chat_thread_members_v1 FOR SELECT
  USING (public.is_chat_thread_member(thread_id, auth.uid()));
