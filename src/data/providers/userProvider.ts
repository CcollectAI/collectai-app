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

/**
 * Drop cached profiles so the next read re-fetches.
 *
 * Profiles now carry privacy-gated stats (collection count / value). The cache
 * lives for the whole session, so without this a user who turns off "Show
 * collection value" would keep seeing the old number on their own profile and
 * reasonably conclude the toggle does nothing — which is exactly the bug this
 * whole change set out to fix.
 */
export function clearProfileCache(): void {
  profileCache.clear();
  myProfileCache = undefined;
}

export async function getPublicUserProfile(userId: string): Promise<PublicUserProfile | null> {
  if (!userId) return null;

  if (profileCache.has(userId)) {
    return profileCache.get(userId) ?? null;
  }

  // user_public_profile_v1 columns: user_id, display_handle, avatar_url,
  // created_at, updated_at, collection_count, collection_value_eur. Earlier
  // code selected display_name, username, bio, level, total_xp etc. that don't
  // exist on the view — they 400'd silently. The mapper falls back gracefully
  // when a field isn't present.
  //
  // collection_count / collection_value_eur come back NULL when the owner has
  // turned off "Show item count" / "Show collection value" in Settings →
  // Privacy. The gate is in the view (20260804_privacy_settings_enforcement),
  // not here — a check in this file would be advisory, since the app reads the
  // view directly over PostgREST.
  const profileCols =
    'user_id, display_handle, avatar_url, created_at, collection_count, collection_value_eur';
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
    /**
     * NULL, not the display name again.
     *
     * `user_public_profile_v1` exposes ONE identity column, `display_handle`,
     * and this mapper used to put it in both fields — so every profile
     * rendered the same string twice, once as the name and once as
     * "@Lena V." with an at-sign in front of a name that has a space and a
     * full stop in it. Seen on the sim 2026-08-20.
     *
     * The screen already branches on `handle` being null (a bare "@" reads as
     * a truncation bug, docs/ui-playbook.md), and that branch could never be
     * false while this line existed. Null is the honest answer: the view does
     * not carry a handle. Restore this the day the view exposes one.
     */
    handle: null,
    avatarUrl: (row.avatar_url ?? null) as string | null,
    bio: null,
    /**
     * NULL means NOT ASKED — and the caller must not render it as zero.
     * `user_public_profile_v1` carries no interests column, so this has always
     * been null here, while `UserStatsSection` rendered
     * `interests?.length ?? 0` as a hard "0 Categories" directly above a
     * Collects list showing six of them ([[learning_empty_answer_rendered_as_zero]]).
     * The stat now reads the same source that list does.
     */
    interests: null,
    collectionCount: (row.collection_count ?? null) as number | null,
    collectionValueEur: (row.collection_value_eur ?? null) as number | null,
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
    // `user_public_profiles` already excludes users who turned off "Allow
    // discovery" (20260804_privacy_settings_enforcement) — the filter is in the
    // view so it cannot be bypassed by calling PostgREST directly. You still
    // match yourself, so opting out never hides you from your own search.
    ({ data, error } = await withTimeout(
      supabase
        .from('user_public_profiles')
        .select(
          'user_id, display_name, handle, avatar_url, bio, interests, collection_count, collection_value_eur',
        )
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
    // THROW, not `return []`. An empty array is indistinguishable from "you
    // have none", so a failed read renders as an empty feature — the house bug
    // class (CLAUDE.md). logger.ERROR because warn is stripped in release.
    logger.error('[SupabaseDataProvider] searchUsers error:', error);
    throw new Error(
      typeof (error as { message?: string })?.message === 'string'
        ? (error as { message: string }).message
        : 'Could not load Users',
    );
  }

  if (!data) return [];

  return (data as Record<string, unknown>[]).map((row) => ({
    id: (row.user_id ?? row.id) as string,
    displayName: (row.display_name as string | null) ?? 'Unknown',
    handle: (row.handle as string | null) ?? null,
    avatarUrl: (row.avatar_url as string | null) ?? null,
    bio: (row.bio as string | null) ?? null,
    interests: (row.interests as string[] | null) ?? null,
    collectionCount: (row.collection_count ?? null) as number | null,
    collectionValueEur: (row.collection_value_eur ?? null) as number | null,
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
    // THROW, not `return []`. An empty array is indistinguishable from "you
    // have none", so a failed read renders as an empty feature — the house bug
    // class (CLAUDE.md). logger.ERROR because warn is stripped in release.
    logger.error('[SupabaseDataProvider] listBlockedUsers error:', error);
    throw new Error(
      typeof (error as { message?: string })?.message === 'string'
        ? (error as { message: string }).message
        : 'Could not load BlockedUsers',
    );
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
