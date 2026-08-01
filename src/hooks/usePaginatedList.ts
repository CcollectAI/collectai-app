/**
 * usePaginatedList -- Generic infinite-scroll / load-more hook.
 *
 * Takes a fetcher `(limit, offset) => Promise<T[]>` and manages:
 *   items[], isLoading, isLoadingMore, hasMore, error
 *
 * Exposes:
 *   loadMore()  -- appends the next page
 *   refresh()   -- resets to the first page
 *
 * The hook is agnostic to the data source; callers wrap their
 * DataProvider / API method in a fetcher closure.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { withTimeout, TimeoutError } from '../lib/withTimeout';
import { onReconnect } from './useNetworkStatus';

// Upper bound on any single page fetch. Deliberately looser than an individual
// provider's own timeout (itemsProvider uses 8s) so this stays a backstop rather
// than the primary mechanism — it exists so the invariant "isLoading always
// clears" holds even for a fetcher that forgot its own guard.
const FETCH_TIMEOUT_MS = 12_000;

// Longest we will wait for `enabled` (auth hydration) before fetching anyway.
// Comfortably longer than a normal cold-start session read, short enough that a
// wedged session costs seconds, not a permanently stuck screen.
const GATE_MAX_WAIT_MS = 5_000;

const DEFAULT_PAGE_SIZE = 20;

export type PaginatedFetcher<T> = (limit: number, offset: number) => Promise<T[]>;

export type UsePaginatedListOptions = {
  /** Items per page (default 20) */
  pageSize?: number;
  /**
   * Defer the initial fetch until this is true. Pass `!auth.loading` so the
   * first query does not fire while the Supabase session is still hydrating.
   *
   * Why: supabase-js queues queries behind its auth lock during hydration, so a
   * query fired too early does not fail fast — it STALLS, burning the full
   * timeout (8s on listItems) before returning empty, and the screen only
   * recovers on the next focus-refetch. Measured on a cold start 2026-07-25.
   *
   * `isLoading` stays true while gated, which is honest: we really are loading.
   * Defaults to true so existing callers are unaffected.
   */
  enabled?: boolean;
};

export type UsePaginatedListReturn<T> = {
  items: T[];
  isLoading: boolean;
  isLoadingMore: boolean;
  hasMore: boolean;
  error: string | null;
  loadMore: () => void;
  refresh: () => void;
  /** Replace items list from the outside (used for optimistic mutations) */
  setItems: React.Dispatch<React.SetStateAction<T[]>>;
};

export function usePaginatedList<T>(
  fetcher: PaginatedFetcher<T>,
  options: UsePaginatedListOptions = {},
): UsePaginatedListReturn<T> {
  const pageSize = options.pageSize ?? DEFAULT_PAGE_SIZE;
  const enabled = options.enabled ?? true;

  const [items, setItems] = useState<T[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Track the current offset to avoid stale closure issues
  const offsetRef = useRef(0);
  // Guard against concurrent fetches
  const fetchingRef = useRef(false);

  // A reconnect that lands while a fetch is still in flight must not be
  // dropped. The offline fetch is typically STILL RUNNING when connectivity
  // returns — it is parked on the 15s supabase timeout — so calling fetchPage
  // straight from the listener hits its `if (fetchingRef.current) return`
  // guard and the refetch silently never happens. That is exactly what shipped
  // in the first version of this fix and failed on device: the offline banner
  // cleared but the list stayed on its empty state.
  const pendingReconnectRefetchRef = useRef(false);


  /**
   * Internal fetch helper.
   * @param reset - if true, resets offset to 0 and replaces items
   */
  const fetchPage = useCallback(
    async (reset: boolean) => {
      if (fetchingRef.current) return;
      fetchingRef.current = true;

      const offset = reset ? 0 : offsetRef.current;

      if (reset) {
        setIsLoading(true);
        setError(null);
      } else {
        setIsLoadingMore(true);
      }

      try {
        // Hard cap on the fetcher, independent of whatever the fetcher itself
        // does. `isLoading` is only cleared in the `finally` below, so a fetcher
        // that never settles pins the skeleton up forever with no error and no
        // retry — the "stuck on skeleton" bug. Individual providers should still
        // use withTimeout (see itemsProvider), but this guarantees the invariant
        // for EVERY caller of this hook (items, alerts, events) including any
        // added later, so the same bug cannot reappear via a new list screen.
        const page = await withTimeout(
          Promise.resolve(fetcher(pageSize, offset)),
          FETCH_TIMEOUT_MS,
          'usePaginatedList.fetcher',
        );
        const receivedLessThanPage = page.length < pageSize;

        if (reset) {
          setItems(page);
          offsetRef.current = page.length;
        } else {
          setItems((prev) => [...prev, ...page]);
          offsetRef.current = offset + page.length;
        }

        setHasMore(!receivedLessThanPage);
      } catch (e: unknown) {
        const message =
          e instanceof TimeoutError
            ? 'Timed out loading. Pull to refresh.'
            : e instanceof Error
              ? e.message
              : 'Failed to load items';
        setError(message);
      } finally {
        setIsLoading(false);
        setIsLoadingMore(false);
        fetchingRef.current = false;

        // Drain a reconnect that arrived while this fetch was in flight.
        if (pendingReconnectRefetchRef.current) {
          pendingReconnectRefetchRef.current = false;
          void fetchPage(true);
        }
      }
    },
    [fetcher, pageSize],
  );

  // Auto-load once the gate opens (defaults to immediately).
  //
  // `didInitialFetchRef` keeps this a ONE-shot: the effect re-runs when
  // `enabled` flips false->true, but must not refire on later re-renders.
  //
  // GATE_MAX_WAIT_MS is the important half. Gating on auth means a wedged
  // session would otherwise hold `enabled` false forever and pin the skeleton —
  // reintroducing the exact bug this hook was just fixed for, by a different
  // route. So the gate is an optimisation with a deadline: wait for auth if it
  // is coming, but fetch anyway rather than wait indefinitely, and let the
  // fetch timeout handle the fallout.
  const didInitialFetchRef = useRef(false);
  useEffect(() => {
    if (didInitialFetchRef.current) return;

    if (enabled) {
      didInitialFetchRef.current = true;
      fetchPage(true);
      return;
    }

    const t = setTimeout(() => {
      if (didInitialFetchRef.current) return;
      didInitialFetchRef.current = true;
      fetchPage(true);
    }, GATE_MAX_WAIT_MS);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

  // Refetch when connectivity comes back.
  //
  // Without this, a list whose fetch failed while offline stays on its EMPTY
  // state after reconnect — and an empty list reads as "you own nothing", not
  // "the fetch failed". Verified on Android 2026-08-01: airplane-mode ON then
  // OFF left the Items tab showing "Start your collection" while the account
  // had 4 items on the server; only a manual pull-to-refresh recovered them.
  // docs/TESTFLIGHT_QA_CHECKLIST.md § 9 requires refresh within ~10s.
  //
  // `onReconnect` already existed but its ONLY consumer was the offline
  // mutation queue, which replays WRITES. Nothing re-fetched READS.
  //
  // Lives here rather than in each screen for the same reason the timeout and
  // the gate deadline do: every list caller gets it, including screens added
  // later.
  useEffect(() => {
    const unsubscribe = onReconnect(() => {
      // Only for lists that have already tried once — otherwise the initial
      // fetch effect above owns the first load.
      if (!didInitialFetchRef.current) return;
      if (fetchingRef.current) {
        pendingReconnectRefetchRef.current = true; // drain when the in-flight one settles
        return;
      }
      fetchPage(true);
    });
    return unsubscribe;
  }, [fetchPage]);

  const loadMore = useCallback((): Promise<void> => {
    if (!hasMore || isLoadingMore || isLoading) return Promise.resolve();
    return fetchPage(false);
  }, [hasMore, isLoadingMore, isLoading, fetchPage]);

  const refresh = useCallback((): Promise<void> => {
    return fetchPage(true);
  }, [fetchPage]);

  return {
    items,
    isLoading,
    isLoadingMore,
    hasMore,
    error,
    loadMore,
    refresh,
    setItems,
  };
}
