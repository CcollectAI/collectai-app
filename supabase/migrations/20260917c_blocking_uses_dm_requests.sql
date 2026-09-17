-- 2026-09-17: make blocking work, and make the DM request path respect it.
--
-- Bodies are the LIVE production definitions (pg_get_functiondef, read
-- 2026-09-17) with only the marked changes — not the repo's 20260221 copy.
--
-- 1. rpc_block_user_v1 could never succeed. After 20260917b fixed its
--    search_path, a rolled-back call on production failed with
--        relation "chat_threads" does not exist
--    It still "auto-declined pending DMs" in the pre-rewrite chat_threads
--    table. Pending requests live in chat_dm_requests_v1 now; a decline there is
--    status='denied' + decided_at + decided_by (as rpc_decide_dm_request_v1
--    writes it). Both directions, because blocking is symmetric
--    (server/app/lib/blocks.py).
--
-- 2. rpc_request_dm_v1 did not look at user_blocks. The app is the only thing
--    that checked (isBlocked in chat/new), so a blocked member could still send
--    a request through the API. EC2's send-message route and the P2P routes
--    already enforce blocks through app/lib/blocks.py; this is the path that
--    never touches EC2.
--
-- 3. rpc_decide_dm_request_v1 could APPROVE a request between two members
--    where one has blocked the other, creating the thread the block was meant
--    to prevent. Declining stays allowed.
--
-- Signatures, SECURITY DEFINER and search_path are unchanged, so
-- scripts/rpc.lock.json (names + params) is unaffected.

BEGIN;

CREATE OR REPLACE FUNCTION public.rpc_block_user_v1(p_target_id uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path = public, pg_temp
AS $function$
DECLARE
  v_uid uuid := auth.uid();
BEGIN
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  IF v_uid = p_target_id THEN
    RAISE EXCEPTION 'Cannot block yourself';
  END IF;

  -- Insert block (ignore if already exists)
  INSERT INTO public.user_blocks (blocker_id, blocked_id)
  VALUES (v_uid, p_target_id)
  ON CONFLICT (blocker_id, blocked_id) DO NOTHING;

  -- CHANGED 2026-09-17: decline pending DM requests in either direction, in
  -- the table that holds them (was: UPDATE chat_threads, which no longer exists).
  UPDATE public.chat_dm_requests_v1
     SET status = 'denied', decided_at = now(), decided_by = v_uid
   WHERE status = 'pending'
     AND (
       (requester_id = v_uid AND target_user_id = p_target_id) OR
       (requester_id = p_target_id AND target_user_id = v_uid)
     );
END;
$function$;

CREATE OR REPLACE FUNCTION public.rpc_request_dm_v1(p_target_user_id uuid, p_context jsonb DEFAULT '{}'::jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path = public
AS $function$
declare
  v_user uuid;
  v_id uuid;
begin
  v_user := auth.uid();
  if v_user is null then raise exception 'not_authenticated'; end if;
  if p_target_user_id is null or p_target_user_id = v_user then raise exception 'invalid_target'; end if;

  -- CHANGED 2026-09-17: a block in either direction refuses the request.
  if exists (
    select 1 from public.user_blocks
     where (blocker_id = v_user and blocked_id = p_target_user_id)
        or (blocker_id = p_target_user_id and blocked_id = v_user)
  ) then
    raise exception 'blocked';
  end if;

  insert into public.chat_dm_requests_v1(requester_id, target_user_id, context)
  values (v_user, p_target_user_id, coalesce(p_context,'{}'::jsonb))
  returning id into v_id;

  return jsonb_build_object('request_id', v_id, 'status', 'pending');
end $function$;

CREATE OR REPLACE FUNCTION public.rpc_decide_dm_request_v1(p_request_id uuid, p_approve boolean)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path = public
AS $function$
declare
  v_user uuid;
  r record;
  v_a uuid;
  v_b uuid;
  v_thread_id uuid;
begin
  v_user := auth.uid();
  if v_user is null then raise exception 'not_authenticated'; end if;

  select * into r
  from public.chat_dm_requests_v1
  where id = p_request_id;

  if r.id is null then raise exception 'not_found'; end if;
  if r.target_user_id <> v_user then raise exception 'not_allowed'; end if;
  if r.status <> 'pending' then
    return jsonb_build_object('request_id', r.id, 'status', r.status, 'thread_id', r.thread_id);
  end if;

  if not p_approve then
    update public.chat_dm_requests_v1
      set status='denied', decided_at=now(), decided_by=v_user
    where id = r.id;
    return jsonb_build_object('request_id', r.id, 'status', 'denied');
  end if;

  -- CHANGED 2026-09-17: never open a thread across a block.
  if exists (
    select 1 from public.user_blocks
     where (blocker_id = r.requester_id and blocked_id = r.target_user_id)
        or (blocker_id = r.target_user_id and blocked_id = r.requester_id)
  ) then
    raise exception 'blocked';
  end if;

  -- canonicalize pair for unique DM thread
  v_a := least(r.requester_id, r.target_user_id);
  v_b := greatest(r.requester_id, r.target_user_id);

  -- create thread (or reuse if exists)
  insert into public.chat_threads_v1(kind, created_by, dm_user_a, dm_user_b)
  values ('dm', v_user, v_a, v_b)
  on conflict (kind, dm_user_a, dm_user_b) do update set updated_at=now()
  returning id into v_thread_id;

  -- ensure both members
  insert into public.chat_thread_members_v1(thread_id, user_id, role)
  values (v_thread_id, r.requester_id, 'member')
  on conflict (thread_id, user_id) do nothing;

  insert into public.chat_thread_members_v1(thread_id, user_id, role)
  values (v_thread_id, r.target_user_id, 'member')
  on conflict (thread_id, user_id) do nothing;

  update public.chat_dm_requests_v1
    set status='approved', thread_id=v_thread_id, decided_at=now(), decided_by=v_user
  where id = r.id;

  return jsonb_build_object('request_id', r.id, 'status', 'approved', 'thread_id', v_thread_id);
end $function$;

COMMIT;
