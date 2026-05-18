/**
 * useFollowedCategories — shared hook for reading the user's followed
 * categories. Backed by AsyncStorage (fast, offline-friendly) with a
 * backend refresh on mount.
 *
 * Used by every category picker so onboarding-picked categories surface
 * at the top of the list (add-manual, quickscan, marketplace, wishlist).
 */

import { useEffect, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { collectorsApi } from '@/api/collectorsApi';
import logger from '@/utils/logger';

const STORAGE_KEY = '@sparrowcollect/followed_categories';

export function useFollowedCategories(): { followed: Set<string>; loading: boolean } {
  const [followed, setFollowed] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    AsyncStorage.getItem(STORAGE_KEY)
      .then((raw) => {
        if (cancelled || !raw) return;
        try {
          const parsed = JSON.parse(raw);
          if (Array.isArray(parsed)) setFollowed(new Set(parsed));
        } catch {
          // Stale/corrupt cache — fall through to backend.
        }
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });

    // Refresh from backend in background. Best-effort.
    collectorsApi.getFollowedCategories()
      .then((data) => {
        if (cancelled || !data?.followed_categories) return;
        const next = new Set(data.followed_categories);
        setFollowed(next);
        AsyncStorage.setItem(STORAGE_KEY, JSON.stringify([...next])).catch(() => {});
      })
      .catch((err) => logger.warn('[useFollowedCategories] backend fetch failed', err));

    return () => { cancelled = true; };
  }, []);

  return { followed, loading };
}
