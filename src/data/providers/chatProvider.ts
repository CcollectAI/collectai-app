/**
 * Chat/DM domain provider — inbox threads, messages, typing indicators, DM status.
 */

import type {
  DmThread,
  DmRequest,
  DmMessage,
  DmThreadStatus,
} from '../types';
import { supabase } from '../../lib/supabase';
import logger from '../../utils/logger';
import { withTimeout, TimeoutError } from '../../lib/withTimeout';

// supabase-js has no per-request timeout, so a stalled HTTPS round-trip would
// leave the inbox's `loading` state pinned forever (infinite spinner). Guard
// the loading-gating reads and treat a timeout as an empty result.
const SUPABASE_READ_TIMEOUT_MS = 5_000;

// v_chat_inbox_v1 columns (verified 2026-04-29 against live schema):
// thread_id, user_id, other_user_id, other_avatar_url, other_display_name,
// last_message_body, last_message_at, unread_count, created_at, updated_at.
// Status + is_incoming live in chat_dm_requests_v1, queried separately.

export async function listInboxThreads(): Promise<DmThread[]> {
  try {
    const { data, error } = await withTimeout(
      supabase
        .from('v_chat_inbox_v1')
        .select('thread_id, other_user_id, other_avatar_url, other_display_name, last_message_at, last_message_body, unread_count')
        .order('last_message_at', { ascending: false }),
      SUPABASE_READ_TIMEOUT_MS,
      'listInboxThreads',
    );

    if (error) {
      logger.warn('[SupabaseDataProvider] listInboxThreads error:', error);
      return [];
    }

    if (!data) return [];

    return (data as Record<string, unknown>[]).map((row) => ({
      id: row.thread_id as string,
      otherUserId: row.other_user_id as string,
      otherUserName: (row.other_display_name ?? 'Unknown') as string,
      otherUserHandle: null,
      otherUserAvatarUrl: (row.other_avatar_url ?? null) as string | null,
      otherUserAvatarColor: '#6b7280',
      status: 'accepted' as DmThreadStatus,
      lastMessagePreview: (row.last_message_body ?? null) as string | null,
      lastMessageAt: (row.last_message_at ?? null) as string | null,
      unreadCount: (row.unread_count ?? 0) as number,
      isIncoming: false,
    }));
  } catch (e) {
    if (e instanceof TimeoutError) {
      logger.error('[SupabaseDataProvider] listInboxThreads timed out');
      return [];
    }
    throw e;
  }
}

export async function listIncomingRequests(): Promise<DmRequest[]> {
  try {
    // getSession() reads the LOCAL session (no network) — avoids the extra
    // auth-server round-trip getUser() makes on every inbox open. The user.id
    // is only used to filter; RLS on chat_dm_requests_v1 enforces auth.uid()
    // server-side regardless, so this is safe.
    const { data: { session } } = await withTimeout(
      supabase.auth.getSession(),
      SUPABASE_READ_TIMEOUT_MS,
      'listIncomingRequests.getSession',
    );
    const user = session?.user;
    if (!user) return [];

    const { data, error } = await withTimeout(
      supabase
        .from('chat_dm_requests_v1')
        .select('id, thread_id, requester_id, context, created_at')
        .eq('target_user_id', user.id)
        .eq('status', 'pending')
        .order('created_at', { ascending: false }),
      SUPABASE_READ_TIMEOUT_MS,
      'listIncomingRequests',
    );

    if (error) {
      logger.warn('[SupabaseDataProvider] listIncomingRequests error:', error);
      return [];
    }

    if (!data) return [];

    return (data as Record<string, unknown>[]).map((row) => {
    const ctx = (row.context ?? null) as Record<string, unknown> | null;
    return {
      threadId: (row.thread_id ?? row.id) as string,
      fromUserId: row.requester_id as string,
      fromUserName: 'Unknown',
      fromUserHandle: null,
      fromUserAvatarUrl: null,
      fromUserAvatarColor: '#6b7280',
      requestMessage: (ctx?.message as string | null) ?? null,
      requestedAt: (row.created_at ?? new Date().toISOString()) as string,
    };
    });
  } catch (e) {
    if (e instanceof TimeoutError) {
      logger.error('[SupabaseDataProvider] listIncomingRequests timed out');
      return [];
    }
    throw e;
  }
}

// rpc_request_dm_v1 returns { request_id, status:'pending' } — NOT a
// thread_id. A thread is only created when the target approves via
// rpc_decide_dm_request_v1. The function takes a jsonb `context`; we
// fold the optional plain-string `message` into that under a single
// "message" key so the caller's existing signature still works.
export async function requestDm(toUserId: string, message?: string): Promise<string> {
  const { data, error } = await supabase.rpc('rpc_request_dm_v1', {
    p_target_user_id: toUserId,
    p_context: message ? { message } : {},
  });

  if (error) {
    logger.error('[SupabaseDataProvider] requestDm error:', error);
    throw new Error(error.message || 'Failed to send DM request');
  }

  const result = data as Record<string, unknown> | null;
  return (result?.request_id as string) ?? '';
}

// p_request_id matches chat_dm_requests_v1.id (NOT thread_id — the thread
// doesn't exist yet for pending requests). listIncomingRequests already
// maps `id` into the `threadId` field for backwards compat, so callers
// passing what they call "threadId" are in fact passing the right value.
export async function decideDmRequest(requestId: string, accept: boolean): Promise<void> {
  const { error } = await supabase.rpc('rpc_decide_dm_request_v1', {
    p_request_id: requestId,
    p_approve: accept,
  });

  if (error) {
    logger.error('[SupabaseDataProvider] decideDmRequest error:', error);
    throw new Error(error.message || 'Failed to process DM request');
  }
}

export async function markThreadRead(threadId: string): Promise<void> {
  const { error } = await supabase.rpc('rpc_mark_thread_read_v1', {
    p_thread_id: threadId,
  });

  if (error) {
    logger.warn('[SupabaseDataProvider] markThreadRead error:', error);
  }
}

export async function getThreadMessages(threadId: string): Promise<DmMessage[]> {
  // chat_messages_v1 columns: id, thread_id, user_id, body, created_at,
  // edited_at, deleted_at. Per-message read tracking lives on
  // chat_thread_reads_v1 (thread-level last_read_at), not the message row.
  // Timeout-guarded like the inbox reads: a stalled round-trip would
  // otherwise pin the thread screen's loading state for ~1min.
  try {
    const { data, error } = await withTimeout(
      supabase
        .from('chat_messages_v1')
        .select('id, thread_id, user_id, body, created_at')
        .eq('thread_id', threadId)
        .order('created_at', { ascending: true }),
      SUPABASE_READ_TIMEOUT_MS,
      'getThreadMessages',
    );

    if (error) {
      logger.warn('[SupabaseDataProvider] getThreadMessages error:', error);
      return [];
    }

    if (!data) return [];

    return (data as Record<string, unknown>[]).map((row) => ({
      id: row.id as string,
      threadId: (row.thread_id as string | null) ?? threadId,
      authorUserId: row.user_id as string,
      text: (row.body as string | null) ?? '',
      createdAt: (row.created_at ?? new Date().toISOString()) as string,
      readAt: null,
    }));
  } catch (e) {
    if (e instanceof TimeoutError) {
      logger.error('[SupabaseDataProvider] getThreadMessages timed out');
      return [];
    }
    throw e;
  }
}

export async function sendMessage(threadId: string, body: string): Promise<DmMessage> {
  // Goes through EC2 (POST /chat/threads/{id}/messages) instead of calling
  // rpc_send_message_v1 directly: the EC2 handler fires `_notify_new_message`,
  // which is what makes the message pop up like WhatsApp/iMessage when the
  // recipient's app is closed. The RPC path inserts the row but skips push.
  const { sendChatMessage } = await import('../../api/chatApi');
  const resp = await sendChatMessage(threadId, body);
  const row = resp.message;
  return {
    id: row.id,
    threadId: row.thread_id ?? threadId,
    authorUserId: row.sender_id,
    text: row.body ?? body,
    createdAt: row.created_at ?? new Date().toISOString(),
  };
}

export async function setTyping(threadId: string): Promise<void> {
  const { error } = await supabase.rpc('rpc_set_typing_v1', {
    p_thread_id: threadId,
  });
  if (error) {
    logger.warn('[SupabaseDataProvider] setTyping error:', error);
  }
}

export async function clearTyping(threadId: string): Promise<void> {
  const { error } = await supabase.rpc('rpc_clear_typing_v1', {
    p_thread_id: threadId,
  });
  if (error) {
    logger.warn('[SupabaseDataProvider] clearTyping error:', error);
  }
}

export async function isOtherUserTyping(threadId: string): Promise<boolean> {
  const { data, error } = await supabase.rpc('rpc_get_typing_v1', {
    p_thread_id: threadId,
  });
  if (error || !data) return false;
  const rows = data as { user_id: string; is_typing: boolean }[];
  return rows.some((r) => r.is_typing);
}

export async function getDmStatus(otherUserId: string): Promise<'none' | 'pending_outgoing' | 'pending_incoming' | 'accepted' | 'declined'> {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return 'none';

  // Status lives on chat_dm_requests_v1, not on the inbox view. Look up
  // the most recent request between this pair in either direction.
  const { data, error } = await supabase
    .from('chat_dm_requests_v1')
    .select('status, requester_id, target_user_id, created_at')
    .or(`and(requester_id.eq.${user.id},target_user_id.eq.${otherUserId}),and(requester_id.eq.${otherUserId},target_user_id.eq.${user.id})`)
    .order('created_at', { ascending: false })
    .limit(1)
    .maybeSingle();

  if (error || !data) return 'none';

  const row = data as { status: string; requester_id: string; target_user_id: string };
  if (row.status === 'accepted') return 'accepted';
  if (row.status === 'declined') return 'declined';
  if (row.status === 'pending') {
    return row.target_user_id === user.id ? 'pending_incoming' : 'pending_outgoing';
  }
  return 'none';
}

export async function getInboxUnreadCount(): Promise<number> {
  // accepted threads — sum the per-thread unread_count from the inbox view.
  const { data: threads } = await supabase
    .from('v_chat_inbox_v1')
    .select('unread_count');
  let total = 0;
  for (const row of (threads ?? []) as { unread_count: number | null }[]) {
    total += row.unread_count ?? 0;
  }

  // pending incoming requests count as 1 each.
  const { data: { user } } = await supabase.auth.getUser();
  if (user) {
    const { count } = await supabase
      .from('chat_dm_requests_v1')
      .select('id', { count: 'exact', head: true })
      .eq('target_user_id', user.id)
      .eq('status', 'pending');
    total += count ?? 0;
  }

  return total;
}
