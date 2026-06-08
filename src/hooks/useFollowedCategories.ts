/**
 * useFollowedCategories — shared hook for reading the user's followed
 * categories. Backed by the shared followedCategoriesStore (AsyncStorage +
 * in-memory pub/sub) so a Follow/Unfollow anywhere in the app propagates to
 * every consumer synchronously — no remount required.
 *
 * Used by every category picker so onboarding-picked categories surface
 * at the top of the list (add-manual, quickscan, marketplace, wishlist) and
 * by the Events tab "My Categories" filter.
 */

import { useEffect, useState } from 'react';
import { collectorsApi } from '@/api/collectorsApi';
import { followedCategoriesStore } from '@/data/followedCategoriesStore';
import logger from '@/utils/logger';

export function useFollowedCategories(): { followed: Set<string>; loading: boolean } {
  const [followed, setFollowed] = useState<Set<string>>(() => followedCategoriesStore.get());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    // Live updates: any add/remove/setAll re-renders this consumer.
    const unsubscribe = followedCategoriesStore.subscribe(setFollowed);

    // Fast offline-friendly first paint.
    followedCategoriesStore.loadFromStorage()
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });

    // Refresh from backend in background. Best-effort.
    collectorsApi.getFollowedCategories()
      .then((data) => {
        if (cancelled || !data?.followed_categories) return;
        followedCategoriesStore.setAll(data.followed_categories);
      })
      .catch((err) => logger.warn('[useFollowedCategories] backend fetch failed', err));

    return () => { cancelled = true; unsubscribe(); };
  }, []);

  return { followed, loading };
}
