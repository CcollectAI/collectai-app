/**
 * User domain provider — profiles, search, blocking.
 */

import type { PublicUserProfile } from '../types';
import { supabase } from '../../lib/supabase';
import { withTimeout } from '../../lib/withTimeout';
import logger from '../../utils/logger';

// In-memory profile cache to prevent repeated lookups
const profileCache: Map<string, PublicUserProfile | null> = new Map();
let myProfileCache: PublicUserProfile | null | undefined = undefined;

export async function getPublicUserProfile(userId: string): Promise<PublicUserProfile | null> {
  if (!userId) return null;

  if (profileCache.has(userId)) {
    return profileCache.get(userId) ?? null;
  }

  // user_public_profile_v1 columns: user_id, display_handle,
  // avatar_url, created_at, updated_at. Earlier code selected display_name,
  // username, bio, level, total_xp etc. that don't exist on the view —
  // they 400'd silently. The mapper falls back gracefully when a field
  // isn't present.
  const profileCols = 'user_id, display_handle, avatar_url, created_at';
  const { data, error } = await supabase
    .from('user_public_profile_v1')
    .select(profileCols)
    .eq('user_id', userId)
    .maybeSingle();

  if (error) {
    if (error.code === 'PGRST116') {
      profileCache.set(userId, null);
      return null;
    }
    logger.warn('[SupabaseDataProvider] getPublicUserProfile error:', error);
    return null;
  }

  if (!data) {
    profileCache.set(userId, null);
    return null;
  }

  const row = data as Record<string, unknown>;

  const profile: PublicUserProfile = {
    id: (row.user_id ?? userId) as string,
    displayName: (row.display_handle ?? 'Unknown') as string,
    handle: (row.display_handle ?? null) as string | null,
    avatarUrl: (row.avatar_url ?? null) as string | null,
    bio: null,
    interests: null,
    collectionCount: null,
    collectionValueEur: null,
  };

  profileCache.set(userId, profile);
  return profile;
}

export async function getMyProfile(): Promise<PublicUserProfile | null> {
  if (myProfileCache !== undefined) {
    return myProfileCache;
  }

  const { data: { user }, error: authError } = await supabase.auth.getUser();
  if (authError || !user) {
    logger.warn('[SupabaseDataProvider] getMyProfile: not authenticated');
    myProfileCache = null;
    return null;
  }

  const profile = await getPublicUserProfile(user.id);
  myProfileCache = profile;
  return profile;
}

export async function searchUsers(query: string): Promise<PublicUserProfile[]> {
  if (!query.trim()) return [];

  const pattern = `%${query.trim()}%`;

  // supabase-js has no per-request timeout; without this a stalled round-trip
  // pins the "Find friends" spinner forever. Time out to [] so the caller falls
  // through to its existing "No collectors found" empty state.
  let data: unknown;
  let error: unknown;
  try {
    ({ data, error } = await withTimeout(
      supabase
        .from('user_public_profiles')
        .select('user_id, display_name, handle, avatar_url, bio, interests')
        .or(`display_name.ilike.${pattern},handle.ilike.${pattern}`)
        .limit(20),
      5_000,
      'searchUsers',
    ));
  } catch (e) {
    logger.error('[SupabaseDataProvider] searchUsers timed out or threw:', e);
    return [];
  }

  if (error) {
    logger.warn('[SupabaseDataProvider] searchUsers error:', error);
    return [];
  }

  if (!data) return [];

  return (data as Record<string, unknown>[]).map((row) => ({
    id: (row.user_id ?? row.id) as string,
    displayName: (row.display_name as string | null) ?? 'Unknown',
    handle: (row.handle as string | null) ?? null,
    avatarUrl: (row.avatar_url as string | null) ?? null,
    bio: (row.bio as string | null) ?? null,
    interests: (row.interests as string[] | null) ?? null,
  }));
}

export async function blockUser(userId: string): Promise<void> {
  const { error } = await supabase.rpc('rpc_block_user_v1', {
    p_target_id: userId,
  });
  if (error) {
    logger.error('[SupabaseDataProvider] blockUser error:', error);
    throw new Error(error.message || 'Failed to block user');
  }
}

export async function unblockUser(userId: string): Promise<void> {
  const { error } = await supabase.rpc('rpc_unblock_user_v1', {
    p_target_id: userId,
  });
  if (error) {
    logger.error('[SupabaseDataProvider] unblockUser error:', error);
    throw new Error(error.message || 'Failed to unblock user');
  }
}

export async function listBlockedUsers(): Promise<{ id: string; name: string }[]> {
  const { data, error } = await supabase.rpc('rpc_list_blocked_v1');
  if (error) {
    logger.warn('[SupabaseDataProvider] listBlockedUsers error:', error);
    return [];
  }

  const rows = (data ?? []) as { blocked_id: string }[];

  const settled = await Promise.allSettled(
    rows.map((row) => getPublicUserProfile(row.blocked_id)),
  );

  return rows.map((row, i) => {
    const result = settled[i];
    const profile = result.status === 'fulfilled' ? result.value : null;
    return {
      id: row.blocked_id,
      name: (profile as { displayName?: string } | null)?.displayName ?? 'Unknown',
    };
  });
}

export async function isBlocked(userId: string): Promise<boolean> {
  const { data, error } = await supabase.rpc('rpc_is_blocked_v1', {
    p_other_id: userId,
  });
  if (error) {
    logger.warn('[SupabaseDataProvider] isBlocked error:', error);
    return false;
  }
  return data === true;
}
