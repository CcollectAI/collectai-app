import { renderHook, act, waitFor } from '@testing-library/react-native';
import { usePaginatedList } from '../../src/hooks/usePaginatedList';

describe('usePaginatedList', () => {
  it('starts with isLoading=true and empty items', () => {
    const fetcher = jest.fn().mockResolvedValue([]);
    const { result } = renderHook(() => usePaginatedList(fetcher));
    expect(result.current.isLoading).toBe(true);
    expect(result.current.items).toEqual([]);
  });

  it('fetches first page on mount and sets items', async () => {
    const data = [{ id: 1 }, { id: 2 }, { id: 3 }];
    const fetcher = jest.fn().mockResolvedValue(data);
    const { result } = renderHook(() => usePaginatedList(fetcher, { pageSize: 20 }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.items).toEqual(data);
    expect(fetcher).toHaveBeenCalledWith(20, 0);
  });

  it('sets hasMore=false when results are fewer than pageSize', async () => {
    const fetcher = jest.fn().mockResolvedValue([{ id: 1 }]);
    const { result } = renderHook(() => usePaginatedList(fetcher, { pageSize: 20 }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.hasMore).toBe(false);
  });

  it('sets hasMore=true when results equal pageSize', async () => {
    const page = Array.from({ length: 10 }, (_, i) => ({ id: i }));
    const fetcher = jest.fn().mockResolvedValue(page);
    const { result } = renderHook(() => usePaginatedList(fetcher, { pageSize: 10 }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.hasMore).toBe(true);
  });

  it('loadMore appends next page and sets isLoadingMore', async () => {
    const page1 = Array.from({ length: 5 }, (_, i) => ({ id: i }));
    const page2 = [{ id: 10 }, { id: 11 }];
    const fetcher = jest.fn()
      .mockResolvedValueOnce(page1)
      .mockResolvedValueOnce(page2);

    const { result } = renderHook(() => usePaginatedList(fetcher, { pageSize: 5 }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    expect(result.current.items).toEqual(page1);

    await act(async () => {
      result.current.loadMore();
    });

    await waitFor(() => {
      expect(result.current.isLoadingMore).toBe(false);
    });

    expect(result.current.items).toEqual([...page1, ...page2]);
    expect(fetcher).toHaveBeenCalledWith(5, 5);
  });

  it('loadMore is a no-op when hasMore=false', async () => {
    const fetcher = jest.fn().mockResolvedValue([{ id: 1 }]);
    const { result } = renderHook(() => usePaginatedList(fetcher, { pageSize: 20 }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    expect(result.current.hasMore).toBe(false);

    await act(async () => {
      result.current.loadMore();
    });

    // Should not have fetched again
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('refresh resets offset and replaces items', async () => {
    const page1 = [{ id: 1 }, { id: 2 }];
    const refreshed = [{ id: 3 }, { id: 4 }];
    const fetcher = jest.fn()
      .mockResolvedValueOnce(page1)
      .mockResolvedValueOnce(refreshed);

    const { result } = renderHook(() => usePaginatedList(fetcher, { pageSize: 20 }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    expect(result.current.items).toEqual(page1);

    await act(async () => {
      result.current.refresh();
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.items).toEqual(refreshed);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it('sets error when fetcher throws', async () => {
    const fetcher = jest.fn().mockRejectedValue(new Error('Network fail'));
    const { result } = renderHook(() => usePaginatedList(fetcher));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBeTruthy();
    expect(result.current.items).toEqual([]);
  });

  it('respects custom pageSize option', async () => {
    const fetcher = jest.fn().mockResolvedValue([]);
    renderHook(() => usePaginatedList(fetcher, { pageSize: 50 }));

    await waitFor(() => {
      expect(fetcher).toHaveBeenCalledWith(50, 0);
    });
  });
});

/**
 * The gap that let the "stuck on skeleton" bug exist.
 *
 * Every test above resolves or rejects. None covered a fetcher that does
 * NEITHER — and that is the production failure: supabase-js ships no
 * per-request timeout, so a stalled TLS handshake / captive portal / server hang
 * left the promise pending forever. `isLoading` is only cleared in `finally`, so
 * the Items skeleton stayed up with no error, no retry and nothing in the logs
 * (logger.warn is stripped in release builds).
 *
 * Reported 2026-07-25. Fixed in two layers: itemsProvider.listItems now wraps its
 * query in withTimeout(8s), and this hook caps ANY fetcher at 12s so the
 * invariant holds for every caller — items, alerts, events, and any list screen
 * added later.
 *
 * Teeth: drop the withTimeout wrapper from fetchPage and this block hangs to the
 * jest timeout and fails.
 */
describe('usePaginatedList — a hanging fetcher must not pin the skeleton', () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  it('clears isLoading and reports a timeout when the fetcher never settles', async () => {
    const neverSettles = jest.fn(() => new Promise<unknown[]>(() => {}));
    const { result } = renderHook(() => usePaginatedList(neverSettles as never));

    // Skeleton up while genuinely in flight — correct.
    expect(result.current.isLoading).toBe(true);

    await act(async () => {
      jest.advanceTimersByTime(13_000); // past the hook's FETCH_TIMEOUT_MS
    });

    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toMatch(/timed out/i);
  });
});
