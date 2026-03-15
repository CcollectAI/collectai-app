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

export async function listInboxThreads(): Promise<DmThread[]> {
  const { data, error } = await supabase
    .from('v_chat_inbox_v1')
    .select('id, thread_id, other_user_id, other_user_name, other_user_handle, other_user_avatar_url, other_user_avatar_color, last_message_at, last_message_preview, unread_count, status, is_incoming')
    .order('last_message_at', { ascending: false });

  if (error) {
    logger.warn('[SupabaseDataProvider] listInboxThreads error:', error);
    return [];
  }

  if (!data) return [];

  return (data as Record<string, unknown>[]).map((row) => ({
    id: (row.id ?? row.thread_id) as string,
    otherUserId: (row.other_user_id ?? row.otherUserId) as string,
    otherUserName: (row.other_user_name ?? row.otherUserName ?? 'Unknown') as string,
    otherUserHandle: (row.other_user_handle ?? row.otherUserHandle ?? null) as string | null,
    otherUserAvatarUrl: (row.other_user_avatar_url ?? row.otherUserAvatarUrl ?? null) as string | null,
    otherUserAvatarColor: (row.other_user_avatar_color ?? '#6b7280') as string,
    status: ((row.status ?? 'accepted') as string) as DmThreadStatus,
    lastMessagePreview: (row.last_message_preview ?? row.lastMessagePreview ?? null) as string | null,
    lastMessageAt: (row.last_message_at ?? row.lastMessageAt ?? null) as string | null,
    unreadCount: (row.unread_count ?? row.unreadCount ?? 0) as number,
    isIncoming: (row.is_incoming ?? row.isIncoming ?? false) as boolean,
  }));
}

export async function listIncomingRequests(): Promise<DmRequest[]> {
  const { data, error } = await supabase
    .from('v_chat_inbox_v1')
    .select('id, thread_id, other_user_id, other_user_name, other_user_handle, other_user_avatar_url, other_user_avatar_color, last_message_at, last_message_preview, status, is_incoming')
    .eq('status', 'pending')
    .eq('is_incoming', true)
    .order('last_message_at', { ascending: false });

  if (error) {
    logger.warn('[SupabaseDataProvider] listIncomingRequests error:', error);
    return [];
  }

  if (!data) return [];

  return (data as Record<string, unknown>[]).map((row) => ({
    threadId: (row.id ?? row.thread_id) as string,
    fromUserId: (row.other_user_id ?? row.otherUserId) as string,
    fromUserName: (row.other_user_name ?? row.otherUserName ?? 'Unknown') as string,
    fromUserHandle: (row.other_user_handle ?? row.otherUserHandle ?? null) as string | null,
    fromUserAvatarUrl: (row.other_user_avatar_url ?? row.otherUserAvatarUrl ?? null) as string | null,
    fromUserAvatarColor: (row.other_user_avatar_color ?? '#6b7280') as string,
    requestMessage: (row.last_message_preview ?? row.lastMessagePreview ?? null) as string | null,
    requestedAt: (row.last_message_at ?? row.lastMessageAt ?? new Date().toISOString()) as string,
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
  const { data, error } = await supabase
    .from('chat_messages_v1')
    .select('id, thread_id, author_user_id, text, created_at, read_at')
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
    authorUserId: (row.author_user_id ?? row.authorUserId) as string,
    text: (row.text as string | null) ?? '',
    createdAt: (row.created_at ?? row.createdAt ?? new Date().toISOString()) as string,
    readAt: (row.read_at as string | null) ?? null,
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
  const { data, error } = await supabase
    .from('v_chat_inbox_v1')
    .select('status, is_incoming')
    .eq('other_user_id', otherUserId)
    .maybeSingle();

  if (error || !data) {
    return 'none';
  }

  const row = data as { status: string; is_incoming: boolean };
  if (row.status === 'accepted') return 'accepted';
  if (row.status === 'declined') return 'declined';
  if (row.status === 'pending') {
    return row.is_incoming ? 'pending_incoming' : 'pending_outgoing';
  }
  return 'none';
}

export async function getInboxUnreadCount(): Promise<number> {
  const { data, error } = await supabase
    .from('v_chat_inbox_v1')
    .select('unread_count, status, is_incoming');

  if (error || !data) {
    return 0;
  }

  const rows = data as { unread_count: number; status: string; is_incoming: boolean }[];

  let total = 0;
  for (const row of rows) {
    if (row.status === 'accepted') {
      total += row.unread_count ?? 0;
    } else if (row.status === 'pending' && row.is_incoming) {
      total += 1;
    }
  }
  return total;
}
