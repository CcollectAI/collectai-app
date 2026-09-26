-- 2FA for the SECURITY DEFINER functions the app calls (2026-09-26).
--
-- 20260926b made every RLS table refuse a password-only (aal1) session of a
-- member with a verified factor. These 16 functions run as their OWNER, past
-- RLS, so they were still open to that session: block/unblock, DM requests and
-- decisions, presence and typing, mark-read, create a project, mark owned.
-- Each gets the same check as its first statement. Bodies are prod's
-- pg_get_functiondef, 2026-09-26, with ONLY that block inserted (reviewed
-- diff); CREATE OR REPLACE keeps owner, grants, names and parameters, so
-- scripts/rpc.lock.json is unaffected.
--
-- anon is unchanged: inside a DEFINER function mfa_satisfied() runs as the
-- owner, and a caller with no uid has no factor, so it returns true.
-- Falsifier: as zz-lifecycle, POST /rest/v1/rpc/rpc_heartbeat_v1 with the
-- password token -> 403/42501 MFA_REQUIRED; with the aal2 token -> 200.

CREATE OR REPLACE FUNCTION public.rpc_block_user_v1(p_target_id uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  v_uid uuid := auth.uid();
BEGIN
  -- 2FA (20260926c): a password-only session of a member with a verified
  -- factor may not act through this DEFINER function (it runs past RLS).
  IF NOT public.mfa_satisfied() THEN
    RAISE EXCEPTION 'Two-factor code required' USING ERRCODE = '42501', HINT = 'MFA_REQUIRED';
  END IF;
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

CREATE OR REPLACE FUNCTION public.rpc_clear_typing_v1(p_thread_id uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
BEGIN
  -- 2FA (20260926c): a password-only session of a member with a verified
  -- factor may not act through this DEFINER function (it runs past RLS).
  IF NOT public.mfa_satisfied() THEN
    RAISE EXCEPTION 'Two-factor code required' USING ERRCODE = '42501', HINT = 'MFA_REQUIRED';
  END IF;
  DELETE FROM public.chat_typing_v1
  WHERE thread_id = p_thread_id
    AND user_id = auth.uid();
END;
$function$;

CREATE OR REPLACE FUNCTION public.rpc_create_build_paint_project_v1(p_title text, p_category text DEFAULT NULL::text, p_category_id text DEFAULT NULL::text, p_item_id uuid DEFAULT NULL::uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  v_uid uuid := auth.uid();
  v_project_id text;
  v_resolved_category_id text;
  v_result jsonb;
BEGIN
  -- 2FA (20260926c): a password-only session of a member with a verified
  -- factor may not act through this DEFINER function (it runs past RLS).
  IF NOT public.mfa_satisfied() THEN
    RAISE EXCEPTION 'Two-factor code required' USING ERRCODE = '42501', HINT = 'MFA_REQUIRED';
  END IF;
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  v_resolved_category_id := p_category_id;
  IF p_item_id IS NOT NULL AND v_resolved_category_id IS NULL THEN
    SELECT category INTO v_resolved_category_id
    FROM public.items
    WHERE id = p_item_id AND user_id = v_uid;
  END IF;

  -- Real columns: name (not title), progress_pct (not percent_complete),
  -- last_updated (not updated_at). is_completed is derived from status.
  INSERT INTO public.build_paint_projects (
    id, user_id, name, category, category_id, item_id,
    progress_pct, status, created_at, last_updated
  ) VALUES (
    gen_random_uuid()::text, v_uid, p_title, p_category, v_resolved_category_id, p_item_id,
    0, 'Backlog', now(), now()
  )
  RETURNING id INTO v_project_id;

  SELECT jsonb_build_object(
    'id', bp.id,
    'title', bp.name,
    'category', bp.category,
    'category_id', bp.category_id,
    'item_id', bp.item_id,
    'status', bp.status,
    'percent_complete', bp.progress_pct,
    'is_completed', (lower(coalesce(bp.status,'')) IN ('finished','completed','displayed')),
    'notes', bp.notes,
    'created_at', bp.created_at,
    'updated_at', bp.last_updated
  ) INTO v_result
  FROM public.build_paint_projects bp
  WHERE bp.id = v_project_id;

  RETURN v_result;
END;
$function$;

CREATE OR REPLACE FUNCTION public.rpc_decide_dm_request_v1(p_request_id uuid, p_approve boolean)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_user uuid;
  r record;
  v_a uuid;
  v_b uuid;
  v_thread_id uuid;
begin
  -- 2FA (20260926c): a password-only session of a member with a verified
  -- factor may not act through this DEFINER function (it runs past RLS).
  IF NOT public.mfa_satisfied() THEN
    RAISE EXCEPTION 'Two-factor code required' USING ERRCODE = '42501', HINT = 'MFA_REQUIRED';
  END IF;
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

CREATE OR REPLACE FUNCTION public.rpc_get_batch_presence_v1(p_user_ids uuid[])
 RETURNS TABLE(user_id uuid, last_seen_at timestamp with time zone, is_online boolean)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
BEGIN
  -- 2FA (20260926c): a password-only session of a member with a verified
  -- factor may not act through this DEFINER function (it runs past RLS).
  IF NOT public.mfa_satisfied() THEN
    RAISE EXCEPTION 'Two-factor code required' USING ERRCODE = '42501', HINT = 'MFA_REQUIRED';
  END IF;
  RETURN QUERY
  SELECT up.user_id, up.last_seen_at,
    CASE WHEN up.last_seen_at > now() - interval '2 minutes' AND up.is_online
         THEN true ELSE false END AS is_online
  FROM user_presence up
  WHERE up.user_id = ANY(p_user_ids)
    AND (
      up.user_id = auth.uid()
      OR COALESCE(
           (SELECT ps.show_online_status
              FROM user_privacy_settings ps
             WHERE ps.user_id = up.user_id),
           false)
    );
END;
$function$;

CREATE OR REPLACE FUNCTION public.rpc_get_presence_v1(p_user_id uuid)
 RETURNS TABLE(user_id uuid, last_seen_at timestamp with time zone, is_online boolean)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
BEGIN
  -- 2FA (20260926c): a password-only session of a member with a verified
  -- factor may not act through this DEFINER function (it runs past RLS).
  IF NOT public.mfa_satisfied() THEN
    RAISE EXCEPTION 'Two-factor code required' USING ERRCODE = '42501', HINT = 'MFA_REQUIRED';
  END IF;
  RETURN QUERY
  SELECT up.user_id, up.last_seen_at,
    -- Consider offline if last heartbeat > 2 minutes ago
    CASE WHEN up.last_seen_at > now() - interval '2 minutes' AND up.is_online
         THEN true ELSE false END AS is_online
  FROM user_presence up
  WHERE up.user_id = p_user_id
    AND (
      up.user_id = auth.uid()
      OR COALESCE(
           (SELECT ps.show_online_status
              FROM user_privacy_settings ps
             WHERE ps.user_id = up.user_id),
           false)
    );
END;
$function$;

CREATE OR REPLACE FUNCTION public.rpc_get_typing_v1(p_thread_id uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_user uuid;
begin
  -- 2FA (20260926c): a password-only session of a member with a verified
  -- factor may not act through this DEFINER function (it runs past RLS).
  IF NOT public.mfa_satisfied() THEN
    RAISE EXCEPTION 'Two-factor code required' USING ERRCODE = '42501', HINT = 'MFA_REQUIRED';
  END IF;
  v_user := nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
  if v_user is null then v_user := auth.uid(); end if;
  if v_user is null then raise exception 'not_authenticated'; end if;

  if not exists (
    select 1 from public.chat_thread_members_v1 m
    where m.thread_id = p_thread_id and m.user_id = v_user
  ) then
    raise exception 'not_allowed';
  end if;

  return jsonb_build_object(
    'thread_id', p_thread_id,
    'typing',
    (
      select coalesce(
        jsonb_agg(jsonb_build_object('user_id', t.user_id) order by t.updated_at desc),
        '[]'::jsonb
      )
      from public.chat_typing_v1 t
      where t.thread_id = p_thread_id
        and t.is_typing = true
        and t.expires_at > now()
        and t.user_id <> v_user
    )
  );
end $function$;

CREATE OR REPLACE FUNCTION public.rpc_go_offline_v1()
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
BEGIN
  -- 2FA (20260926c): a password-only session of a member with a verified
  -- factor may not act through this DEFINER function (it runs past RLS).
  IF NOT public.mfa_satisfied() THEN
    RAISE EXCEPTION 'Two-factor code required' USING ERRCODE = '42501', HINT = 'MFA_REQUIRED';
  END IF;
  UPDATE user_presence
  SET is_online = false, updated_at = now()
  WHERE user_id = auth.uid();
END;
$function$;

CREATE OR REPLACE FUNCTION public.rpc_heartbeat_v1()
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  uid uuid := auth.uid();
BEGIN
  -- 2FA (20260926c): a password-only session of a member with a verified
  -- factor may not act through this DEFINER function (it runs past RLS).
  IF NOT public.mfa_satisfied() THEN
    RAISE EXCEPTION 'Two-factor code required' USING ERRCODE = '42501', HINT = 'MFA_REQUIRED';
  END IF;
  IF uid IS NULL OR NOT EXISTS (SELECT 1 FROM auth.users u WHERE u.id = uid) THEN
    RETURN;
  END IF;

  INSERT INTO user_presence (user_id, last_seen_at, is_online, updated_at)
  VALUES (uid, now(), true, now())
  ON CONFLICT (user_id)
  DO UPDATE SET last_seen_at = now(), is_online = true, updated_at = now();
END;
$function$;

CREATE OR REPLACE FUNCTION public.rpc_is_blocked_v1(p_other_id uuid)
 RETURNS boolean
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  v_uid uuid := auth.uid();
BEGIN
  -- 2FA (20260926c): a password-only session of a member with a verified
  -- factor may not act through this DEFINER function (it runs past RLS).
  IF NOT public.mfa_satisfied() THEN
    RAISE EXCEPTION 'Two-factor code required' USING ERRCODE = '42501', HINT = 'MFA_REQUIRED';
  END IF;
  IF v_uid IS NULL THEN
    RETURN false;
  END IF;

  RETURN EXISTS (
    SELECT 1 FROM user_blocks
    WHERE (blocker_id = v_uid AND blocked_id = p_other_id)
       OR (blocker_id = p_other_id AND blocked_id = v_uid)
  );
END;
$function$;

CREATE OR REPLACE FUNCTION public.rpc_list_blocked_v1()
 RETURNS TABLE(blocked_id uuid, created_at timestamp with time zone)
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
BEGIN
  -- 2FA (20260926c): a password-only session of a member with a verified
  -- factor may not act through this DEFINER function (it runs past RLS).
  IF NOT public.mfa_satisfied() THEN
    RAISE EXCEPTION 'Two-factor code required' USING ERRCODE = '42501', HINT = 'MFA_REQUIRED';
  END IF;
  RETURN QUERY
  SELECT ub.blocked_id, ub.created_at
  FROM user_blocks ub
  WHERE ub.blocker_id = auth.uid()
  ORDER BY ub.created_at DESC;
END;
$function$;

CREATE OR REPLACE FUNCTION public.rpc_mark_category_item_owned_v1(p_category_item_id uuid, p_quantity integer DEFAULT 1, p_notes text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_user_id uuid := auth.uid();
  v_result jsonb;
BEGIN
  -- 2FA (20260926c): a password-only session of a member with a verified
  -- factor may not act through this DEFINER function (it runs past RLS).
  IF NOT public.mfa_satisfied() THEN
    RAISE EXCEPTION 'Two-factor code required' USING ERRCODE = '42501', HINT = 'MFA_REQUIRED';
  END IF;
  -- Validate user is authenticated
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  -- Validate category item exists
  IF NOT EXISTS (SELECT 1 FROM public.category_items WHERE id = p_category_item_id) THEN
    RAISE EXCEPTION 'Category item not found';
  END IF;

  -- Upsert ownership record
  INSERT INTO public.user_category_ownership (user_id, category_item_id, quantity, notes)
  VALUES (v_user_id, p_category_item_id, COALESCE(p_quantity, 1), p_notes)
  ON CONFLICT (user_id, category_item_id)
  DO UPDATE SET
    quantity = EXCLUDED.quantity,
    notes = COALESCE(EXCLUDED.notes, user_category_ownership.notes),
    created_at = now();

  -- Return success
  v_result := jsonb_build_object(
    'success', true,
    'category_item_id', p_category_item_id,
    'quantity', p_quantity
  );

  RETURN v_result;
END;
$function$;

CREATE OR REPLACE FUNCTION public.rpc_mark_thread_read_v1(p_thread_id uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_user uuid;
begin
  -- 2FA (20260926c): a password-only session of a member with a verified
  -- factor may not act through this DEFINER function (it runs past RLS).
  IF NOT public.mfa_satisfied() THEN
    RAISE EXCEPTION 'Two-factor code required' USING ERRCODE = '42501', HINT = 'MFA_REQUIRED';
  END IF;
  -- accept either real auth.uid() OR SQL-editor simulated claims
  v_user := nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
  if v_user is null then
    v_user := auth.uid();
  end if;

  if v_user is null then
    raise exception 'not_authenticated';
  end if;

  -- must be a member
  if not exists (
    select 1
    from public.chat_thread_members_v1 m
    where m.thread_id = p_thread_id
      and m.user_id = v_user
  ) then
    raise exception 'not_allowed';
  end if;

  insert into public.chat_thread_reads_v1(thread_id, user_id, last_read_at, updated_at)
  values (p_thread_id, v_user, now(), now())
  on conflict (thread_id, user_id)
  do update set last_read_at = excluded.last_read_at, updated_at = now();

  return jsonb_build_object(
    'thread_id', p_thread_id,
    'marked_read', true
  );
end $function$;

CREATE OR REPLACE FUNCTION public.rpc_request_dm_v1(p_target_user_id uuid, p_context jsonb DEFAULT '{}'::jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_user uuid;
  v_id uuid;
begin
  -- 2FA (20260926c): a password-only session of a member with a verified
  -- factor may not act through this DEFINER function (it runs past RLS).
  IF NOT public.mfa_satisfied() THEN
    RAISE EXCEPTION 'Two-factor code required' USING ERRCODE = '42501', HINT = 'MFA_REQUIRED';
  END IF;
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

CREATE OR REPLACE FUNCTION public.rpc_set_typing_v1(p_thread_id uuid, p_is_typing boolean DEFAULT true)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_user uuid;
  v_exp timestamptz;
begin
  -- 2FA (20260926c): a password-only session of a member with a verified
  -- factor may not act through this DEFINER function (it runs past RLS).
  IF NOT public.mfa_satisfied() THEN
    RAISE EXCEPTION 'Two-factor code required' USING ERRCODE = '42501', HINT = 'MFA_REQUIRED';
  END IF;
  v_user := nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
  if v_user is null then v_user := auth.uid(); end if;
  if v_user is null then raise exception 'not_authenticated'; end if;

  if not exists (
    select 1 from public.chat_thread_members_v1 m
    where m.thread_id = p_thread_id and m.user_id = v_user
  ) then
    raise exception 'not_allowed';
  end if;

  v_exp := case when coalesce(p_is_typing,true) then now() + interval '12 seconds' else now() end;

  insert into public.chat_typing_v1(thread_id, user_id, is_typing, updated_at, expires_at)
  values (p_thread_id, v_user, coalesce(p_is_typing,true), now(), v_exp)
  on conflict (thread_id, user_id)
  do update set is_typing = excluded.is_typing, updated_at = now(), expires_at = excluded.expires_at;

  return jsonb_build_object('thread_id', p_thread_id, 'user_id', v_user, 'is_typing', coalesce(p_is_typing,true), 'expires_at', v_exp);
end $function$;

CREATE OR REPLACE FUNCTION public.rpc_unblock_user_v1(p_target_id uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  v_uid uuid := auth.uid();
BEGIN
  -- 2FA (20260926c): a password-only session of a member with a verified
  -- factor may not act through this DEFINER function (it runs past RLS).
  IF NOT public.mfa_satisfied() THEN
    RAISE EXCEPTION 'Two-factor code required' USING ERRCODE = '42501', HINT = 'MFA_REQUIRED';
  END IF;
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  DELETE FROM user_blocks
  WHERE blocker_id = v_uid
    AND blocked_id = p_target_id;
END;
$function$;
