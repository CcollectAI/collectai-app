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

// Upper bound on any single page fetch. Deliberately looser than an individual
// provider's own timeout (itemsProvider uses 8s) so this stays a backstop rather
// than the primary mechanism — it exists so the invariant "isLoading always
// clears" holds even for a fetcher that forgot its own guard.
const FETCH_TIMEOUT_MS = 12_000;

const DEFAULT_PAGE_SIZE = 20;

export type PaginatedFetcher<T> = (limit: number, offset: number) => Promise<T[]>;

export type UsePaginatedListOptions = {
  /** Items per page (default 20) */
  pageSize?: number;
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

  const [items, setItems] = useState<T[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Track the current offset to avoid stale closure issues
  const offsetRef = useRef(0);
  // Guard against concurrent fetches
  const fetchingRef = useRef(false);

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
      }
    },
    [fetcher, pageSize],
  );

  // Auto-load on mount
  useEffect(() => {
    fetchPage(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
