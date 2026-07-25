/**
 * followedCategoriesStore — single source of truth for the user's followed
 * categories, shared between every reader (useFollowedCategories) and every
 * writer (category-page Follow button, onboarding "save my picks").
 *
 * Previously the Follow button wrote to the backend + cleared the in-memory
 * CachedDataProvider cache, but `useFollowedCategories` kept its own
 * AsyncStorage snapshot that only refreshed on mount — so following a
 * category had no visible effect on the events filter or any category picker
 * until a remount. This store closes that gap: writers call add/remove/setAll
 * and every mounted consumer updates synchronously.
 *
 * Keyed by category slug (e.g. "pokemon"), matching events.category_id,
 * user_category_follows.category_id, and GET /events/categories/followed.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { logger } from '@/lib/logger';

const STORAGE_KEY = '@sparrowcollect/followed_categories';

type Listener = (followed: Set<string>) => void;

let current = new Set<string>();
let hydrated = false;
const listeners = new Set<Listener>();

function emit(): void {
  const snapshot = new Set(current);
  listeners.forEach((l) => l(snapshot));
}

function persist(): void {
  AsyncStorage.setItem(STORAGE_KEY, JSON.stringify([...current])).catch(() => {
    /* best effort — backend remains source of truth */
  });
}

export const followedCategoriesStore = {
  /** Current snapshot (defensive copy). */
  get(): Set<string> {
    return new Set(current);
  },

  /** Subscribe to changes; returns an unsubscribe fn. */
  subscribe(listener: Listener): () => void {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },

  /** Hydrate from AsyncStorage once (offline-friendly first paint). */
  async loadFromStorage(): Promise<Set<string>> {
    if (hydrated) return new Set(current);
    try {
      const raw = await AsyncStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) current = new Set(parsed);
      }
    } catch (e) {
      logger.error('[silent-catch] followedCategoriesStore.ts:61:', e);
      /* stale/corrupt cache — fall through to backend hydration */
    }
    hydrated = true;
    emit();
    return new Set(current);
  },

  /** Replace the whole set (backend refresh, onboarding save). */
  setAll(categories: string[]): void {
    current = new Set(categories);
    hydrated = true;
    persist();
    emit();
  },

  /** Optimistically add one (Follow). No-op if already present. */
  add(categoryId: string): void {
    if (current.has(categoryId)) return;
    current.add(categoryId);
    persist();
    emit();
  },

  /** Optimistically remove one (Unfollow). No-op if absent. */
  remove(categoryId: string): void {
    if (!current.has(categoryId)) return;
    current.delete(categoryId);
    persist();
    emit();
  },
};
