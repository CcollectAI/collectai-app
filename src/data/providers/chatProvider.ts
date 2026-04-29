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

// v_chat_inbox_v1 columns (verified 2026-04-29 against live schema):
// thread_id, user_id, other_user_id, other_avatar_url, other_display_name,
// last_message_body, last_message_at, unread_count, created_at, updated_at.
// Status + is_incoming live in chat_dm_requests_v1, queried separately.

export async function listInboxThreads(): Promise<DmThread[]> {
  const { data, error } = await supabase
    .from('v_chat_inbox_v1')
    .select('thread_id, other_user_id, other_avatar_url, other_display_name, last_message_at, last_message_body, unread_count')
    .order('last_message_at', { ascending: false });

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
}

export async function listIncomingRequests(): Promise<DmRequest[]> {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return [];

  const { data, error } = await supabase
    .from('chat_dm_requests_v1')
    .select('id, thread_id, requester_id, context, created_at')
    .eq('target_user_id', user.id)
    .eq('status', 'pending')
    .order('created_at', { ascending: false });

  if (error) {
    logger.warn('[SupabaseDataProvider] listIncomingRequests error:', error);
    return [];
  }

  if (!data) return [];

  return (data as Record<string, unknown>[]).map((row) => ({
    threadId: (row.thread_id ?? row.id) as string,
    fromUserId: row.requester_id as string,
    fromUserName: 'Unknown',
    fromUserHandle: null,
    fromUserAvatarUrl: null,
    fromUserAvatarColor: '#6b7280',
    requestMessage: (row.context ?? null) as string | null,
    requestedAt: (row.created_at ?? new Date().toISOString()) as string,
  }));
}

export async function requestDm(toUserId: string, message?: string): Promise<string> {
  const { data, error } = await supabase.rpc('rpc_request_dm_v1', {
    p_to_user_id: toUserId,
    p_message: message ?? null,
  });

  if (error) {
    logger.error('[SupabaseDataProvider] requestDm error:', error);
    throw new Error(error.message || 'Failed to send DM request');
  }

  const result = data as Record<string, unknown> | string | null;
  return (typeof result === 'object' && result !== null ? (result.thread_id as string) : result) ?? '';
}

export async function decideDmRequest(threadId: string, accept: boolean): Promise<void> {
  const { error } = await supabase.rpc('rpc_decide_dm_request_v1', {
    p_thread_id: threadId,
    p_accept: accept,
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
  const { data, error } = await supabase
    .from('chat_messages_v1')
    .select('id, thread_id, user_id, body, created_at')
    .eq('thread_id', threadId)
    .order('created_at', { ascending: true });

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
}

export async function sendMessage(threadId: string, body: string): Promise<DmMessage> {
  const { data: { user } } = await supabase.auth.getUser();
  const currentUserId = user?.id ?? 'unknown';

  const { data, error } = await supabase.rpc('rpc_send_message_v1', {
    p_thread_id: threadId,
    p_text: body,
  });

  if (error) {
    logger.error('[SupabaseDataProvider] sendMessage RPC error:', error);
    throw new Error(error.message || 'Failed to send message');
  }

  if (data && typeof data === 'object') {
    const row = data as Record<string, unknown>;
    return {
      id: (row.id ?? row.message_id ?? `msg-${Date.now()}`) as string,
      threadId: (row.thread_id as string | null) ?? threadId,
      authorUserId: (row.author_user_id as string | null) ?? currentUserId,
      text: (row.text as string | null) ?? body,
      createdAt: (row.created_at as string | null) ?? new Date().toISOString(),
    };
  }

  return {
    id: `msg-${Date.now()}`,
    threadId,
    authorUserId: currentUserId,
    text: body,
    createdAt: new Date().toISOString(),
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
