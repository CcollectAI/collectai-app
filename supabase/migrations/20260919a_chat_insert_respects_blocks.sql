-- 2026-09-19: the chat INSERT policy checks thread membership, not blocks.
--
-- EC2's send-message route has always honoured blocks (app/lib/blocks.py), and
-- 20260917c made rpc_request_dm_v1 / rpc_decide_dm_request_v1 honour them too.
-- What was left is the path that touches neither: a member who is already in a
-- thread can INSERT into chat_messages_v1 straight through PostgREST, because
-- the policy only asks "are you a member of this thread?".
--
-- Blocking is SYMMETRIC here — either direction stops the interaction
-- (server/app/lib/blocks.py, and `is_blocked` queries both directions). The
-- check below mirrors that exactly rather than inventing a one-way rule.
--
-- ⚠️ THE DUPLICATE IS THE TRAP. `chat_messages_v1` carried TWO INSERT policies,
-- `chat_messages_v1_insert_member` and `chat_messages_v1_insert_member_self`,
-- with byte-identical WITH CHECK expressions. Policies for one command are
-- OR'd, so adding the block condition to only one of them would have changed
-- NOTHING — the other still admits the row. The duplicate is dropped here so
-- there is one place to be wrong in future, not two.
--
-- Scope: this is defence in depth. The app sends through EC2
-- (chatProvider.sendMessage -> sendChatMessage -> POST /chat/threads/{id}/messages),
-- and service_role bypasses RLS, so no app path changes behaviour. What changes
-- is that the DATABASE now enforces what the route already did.
--
-- Roles: both policies were PERMISSIVE with no role list (PUBLIC), so the
-- replacement carries no TO clause either.

BEGIN;

DROP POLICY IF EXISTS chat_messages_v1_insert_member_self ON public.chat_messages_v1;
DROP POLICY IF EXISTS chat_messages_v1_insert_member ON public.chat_messages_v1;

CREATE POLICY chat_messages_v1_insert_member
  ON public.chat_messages_v1
  FOR INSERT
  WITH CHECK (
    user_id = auth.uid()
    AND EXISTS (
      SELECT 1
      FROM public.chat_thread_members_v1 m
      WHERE m.thread_id = chat_messages_v1.thread_id
        AND m.user_id = auth.uid()
    )
    -- No other member of this thread is on either side of a block with me.
    --
    -- Via rpc_is_blocked_v1, NOT a direct query on user_blocks. The first
    -- version of this migration joined user_blocks inline and was PROVEN WRONG
    -- in a rolled-back transaction on production: the blocker was refused but
    -- THE BLOCKED PARTY STILL GOT THROUGH — the exact person the rule is for.
    --
    -- `user_blocks` has its own RLS, `blocks_select USING (blocker_id =
    -- auth.uid())`, so only the blocker can see the row. A policy subquery runs
    -- as the INSERTING user, so for the blocked party the row is invisible,
    -- NOT EXISTS is trivially true, and the insert is allowed. A check that
    -- reads a table the caller cannot see is not a check.
    --
    -- rpc_is_blocked_v1 is SECURITY DEFINER and STABLE, already symmetric, and
    -- already search_path-pinned by 20260917b — so it sees both rows and
    -- returns the same answer for either party.
    AND NOT EXISTS (
      SELECT 1
      FROM public.chat_thread_members_v1 om
      WHERE om.thread_id = chat_messages_v1.thread_id
        AND om.user_id <> auth.uid()
        AND public.rpc_is_blocked_v1(om.user_id)
    )
  );

COMMIT;
