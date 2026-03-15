/**
 * Presence domain provider — heartbeat, online/offline, batch presence.
 */

import type { UserPresence } from '../types';
import { supabase } from '../../lib/supabase';
import logger from '../../utils/logger';

export async function sendHeartbeat(): Promise<void> {
  try {
    await supabase.rpc('rpc_heartbeat_v1');
  } catch (err: unknown) {
    logger.warn('[SupabaseDataProvider] heartbeat error:', err);
  }
}

export async function goOffline(): Promise<void> {
  try {
    await supabase.rpc('rpc_go_offline_v1');
  } catch (err: unknown) {
    logger.warn('[SupabaseDataProvider] goOffline error:', err);
  }
}

export async function getUserPresence(userId: string): Promise<UserPresence | null> {
  try {
    const { data } = await supabase.rpc('rpc_get_presence_v1', { p_user_id: userId });
    if (!data || (Array.isArray(data) && data.length === 0)) return null;
    const row = Array.isArray(data) ? data[0] : data;
    return {
      userId: row.user_id,
      lastSeenAt: row.last_seen_at,
      isOnline: row.is_online,
    };
  } catch {
    return null;
  }
}

export async function getBatchPresence(userIds: string[]): Promise<UserPresence[]> {
  try {
    const { data } = await supabase.rpc('rpc_get_batch_presence_v1', { p_user_ids: userIds });
    return (data || []).map((row: Record<string, unknown>) => ({
      userId: row.user_id as string,
      lastSeenAt: row.last_seen_at as string,
      isOnline: row.is_online as boolean,
    }));
  } catch {
    return [];
  }
}
