/**
 * useFavorites — the heart's state, shared by every card on screen.
 *
 * ONE FETCH, NOT ONE PER CARD. This is a module-level store rather than
 * per-hook state on purpose: a grid renders 20+ cards, each needs to know
 * whether ITS listing is favourited, and a naive `useEffect(fetch)` inside the
 * hook would fire 20 identical requests on mount and 20 more on every remount.
 * `GET /favorites/ids` exists precisely so the answer is one round trip; a
 * per-instance hook would have thrown that away.
 *
 * Subscribers share one Set and one in-flight promise. A toggle anywhere
 * updates every card rendering that target — including the heart on the
 * Favourites screen itself.
 *
 * This hook does NOT touch the watchlist. Favouriting is "saved" and promises
 * nothing; watching carries a target price and an alert. See the note at the
 * top of src/api/favoritesApi.ts for the bug that conflating them produced.
 */
import { useCallback, useEffect, useState } from 'react';
import {
  fetchFavoriteIds,
  addFavorite,
  removeFavorite,
  type FavoriteTarget,
} from '@/api/favoritesApi';
import { useAuthContext } from '@/providers/useAuthContext';
import logger from '@/utils/logger';

/** The stored key for a target — mirrors the server's COALESCE in /favorites/ids. */
function targetKey(target: FavoriteTarget): string {
  return (target.listing_id ?? target.canonical_key)!;
}

// ─── shared store ────────────────────────────────────────────────────────────
let ids: Set<string> = new Set();
let loaded = false;
let inFlight: Promise<void> | null = null;
const subscribers = new Set<(next: Set<string>) => void>();

function publish(next: Set<string>) {
  ids = next;
  subscribers.forEach((fn) => fn(next));
}

/** One fetch, however many callers. Later callers await the same promise. */
function ensureLoaded(): Promise<void> {
  if (loaded) return Promise.resolve();
  if (inFlight) return inFlight;
  inFlight = fetchFavoriteIds()
    .then((next) => {
      loaded = true;
      publish(next);
    })
    .catch((err) => {
      // logger.error, not warn: info/warn are STRIPPED from release builds,
      // which is exactly where a silently empty heart state would matter
      // (learning_prod_logger_strips_info_warn).
      logger.error('[favorites] id fetch failed:', err);
      // NOT marked loaded — a failure must be retryable on the next mount
      // rather than caching "nothing is favourited" for the whole session.
    })
    .finally(() => {
      inFlight = null;
    });
  return inFlight;
}

/** Drop the cache — call after sign-out, or one member sees another's hearts. */
export function resetFavoritesCache(): void {
  loaded = false;
  inFlight = null;
  publish(new Set());
}

export function useFavorites() {
  const { loading: authLoading } = useAuthContext();
  const [snapshot, setSnapshot] = useState<Set<string>>(ids);

  useEffect(() => {
    subscribers.add(setSnapshot);
    return () => {
      subscribers.delete(setSnapshot);
    };
  }, []);

  useEffect(() => {
    // Don't fire before the session has hydrated. An authed read on cold start
    // goes out with no bearer token and comes back 401, and supabase-js queues
    // it behind the auth lock rather than failing fast
    // (project_2026_07_14_401_root_cause_tokenless).
    if (authLoading) return;
    ensureLoaded();
  }, [authLoading]);

  const isFavorite = useCallback(
    (target: FavoriteTarget) => snapshot.has(targetKey(target)),
    [snapshot],
  );

  /**
   * Flip it. Optimistic, because a heart that waits for a round trip feels
   * broken — but it ROLLS BACK on failure rather than leaving the UI asserting
   * something the server rejected. Returns the new state so a caller can fire
   * the right toast.
   */
  const toggle = useCallback(
    async (target: FavoriteTarget, category?: string | null): Promise<boolean> => {
      const key = targetKey(target);
      const wasFavorite = ids.has(key);

      const optimistic = new Set(ids);
      if (wasFavorite) optimistic.delete(key);
      else optimistic.add(key);
      publish(optimistic);

      try {
        if (wasFavorite) await removeFavorite(target);
        else await addFavorite(target, category);
        return !wasFavorite;
      } catch (err) {
        logger.error('[favorites] toggle failed:', err);
        const rolledBack = new Set(ids);
        if (wasFavorite) rolledBack.add(key);
        else rolledBack.delete(key);
        publish(rolledBack);
        throw err;
      }
    },
    [],
  );

  return { isFavorite, toggle, loading: !loaded };
}
