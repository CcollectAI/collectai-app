/**
 * Marking an alert read has to survive the next fetch.
 *
 * 2026-09-17, sweeping the "success without a write" class. Three independent
 * bugs stacked on this one action:
 *
 *   1. the server answered `{"ok": true}` when the UPDATE matched no row, and
 *      when the query itself failed (`alerts_feature_router.mark_trigger_read`);
 *   2. this hook hardcoded `isRead: false` while the server had been returning
 *      `read` all along, so a successful write was invisible — the alert came
 *      back as new, `unreadOnly` filtered nothing;
 *   3. the feed is cached TTL_MEDIUM and nothing cleared it after the write.
 *
 * And the optimistic flip had no rollback, so the failure of 1 looked like a
 * success until the cache expired. These tests pin all four.
 */
import { renderHook, act, waitFor } from '@testing-library/react-native';
import { useAlertsFeed } from '../../src/hooks/useAlertsFeed';

const mockListAlertsFeed = jest.fn();
const mockListItems = jest.fn();
const mockMarkTriggerRead = jest.fn();
const mockClearAlertsFeedCache = jest.fn();

jest.mock('../../src/data', () => ({
  dataProvider: {
    listAlertsFeed: (...a: unknown[]) => mockListAlertsFeed(...a),
    listItems: (...a: unknown[]) => mockListItems(...a),
  },
}));

jest.mock('../../src/api/collectorsApi', () => ({
  collectorsApi: {
    markTriggerRead: (...a: unknown[]) => mockMarkTriggerRead(...a),
  },
}));

jest.mock('../../src/data/CachedDataProvider', () => ({
  clearAlertsFeedCache: (...a: unknown[]) => mockClearAlertsFeedCache(...a),
}));

jest.mock('../../src/lib/logger', () => ({
  logger: { warn: jest.fn(), info: jest.fn(), error: jest.fn() },
}));

jest.mock('../../src/config/featureFlags', () => ({
  featureFlags: { FEATURE_DATA_INSIGHTS_ALERTS: true },
}));

const UUID_A = '11111111-1111-1111-1111-111111111111';
const UUID_B = '22222222-2222-2222-2222-222222222222';

function feedItem(id: string, read: boolean) {
  return {
    id,
    type: 'price_drop',
    title: 'Charizard — €195 on eBay',
    body: null,
    createdAt: '2026-09-17T10:00:00.000Z',
    itemId: null,
    watchlistItemId: null,
    price: 195,
    targetPrice: 280,
    read,
  };
}

/** An item that produces a DERIVED alert (price under q10). */
const DERIVED_ITEM = {
  id: 'item-derived',
  name: 'Umbreon',
  category: 'pokemon',
  price: 10,
  priceBand: { q10: 50, q50: 80, q90: 120 },
  updatedAt: '2026-09-17T09:00:00.000Z',
};

beforeEach(() => {
  jest.clearAllMocks();
  mockListItems.mockResolvedValue([]);
  mockMarkTriggerRead.mockResolvedValue(undefined);
  mockClearAlertsFeedCache.mockResolvedValue(undefined);
});

async function renderFeed(opts = {}) {
  const hook = renderHook(() => useAlertsFeed({ limit: 10, ...opts }));
  await waitFor(() => expect(hook.result.current.isLoading).toBe(false));
  return hook;
}

describe('the server owns the read flag', () => {
  it('shows an already-read alert as read', async () => {
    mockListAlertsFeed.mockResolvedValue([feedItem(UUID_A, true)]);
    const { result } = await renderFeed();
    expect(result.current.alerts).toHaveLength(1);
    expect(result.current.alerts[0].isRead).toBe(true);
    expect(result.current.unreadCount).toBe(0);
  });

  it('unreadOnly can actually filter, because read is not always false', async () => {
    mockListAlertsFeed.mockResolvedValue([feedItem(UUID_A, true), feedItem(UUID_B, false)]);
    const { result } = await renderFeed({ unreadOnly: true });
    expect(result.current.alerts.map((a) => a.id)).toEqual([UUID_B]);
  });
});

describe('markAsRead', () => {
  it('persists, and clears the cached feed so the next read agrees', async () => {
    mockListAlertsFeed.mockResolvedValue([feedItem(UUID_A, false)]);
    const { result } = await renderFeed();

    await act(async () => { await result.current.markAsRead(UUID_A); });

    expect(mockMarkTriggerRead).toHaveBeenCalledWith(UUID_A);
    expect(mockClearAlertsFeedCache).toHaveBeenCalledTimes(1);
    expect(result.current.alerts[0].isRead).toBe(true);
  });

  it('rolls the row back when the write fails', async () => {
    mockListAlertsFeed.mockResolvedValue([feedItem(UUID_A, false)]);
    mockMarkTriggerRead.mockRejectedValue(new Error('503 DB_ERROR'));
    const { result } = await renderFeed();

    await act(async () => { await result.current.markAsRead(UUID_A); });

    expect(result.current.alerts[0].isRead).toBe(false);
    expect(result.current.unreadCount).toBe(1);
    expect(mockClearAlertsFeedCache).not.toHaveBeenCalled();
  });

  it('never sends a derived id to the trigger-history endpoint', async () => {
    mockListAlertsFeed.mockResolvedValue([]);
    mockListItems.mockResolvedValue([DERIVED_ITEM]);
    const { result } = await renderFeed();
    const derivedId = result.current.alerts[0].id;
    expect(derivedId).toMatch(/^derived-/);

    await act(async () => { await result.current.markAsRead(derivedId); });

    expect(mockMarkTriggerRead).not.toHaveBeenCalled();
    // Still flipped locally: it is the member's own dismissal of a computed row.
    expect(result.current.alerts[0].isRead).toBe(true);
  });
});

describe('markAllAsRead', () => {
  it('rolls back only the rows that failed', async () => {
    mockListAlertsFeed.mockResolvedValue([feedItem(UUID_A, false), feedItem(UUID_B, false)]);
    mockMarkTriggerRead.mockImplementation((id: string) =>
      id === UUID_B ? Promise.reject(new Error('503')) : Promise.resolve()
    );
    const { result } = await renderFeed();

    await act(async () => { await result.current.markAllAsRead(); });

    const byId = Object.fromEntries(result.current.alerts.map((a) => [a.id, a.isRead]));
    expect(byId[UUID_A]).toBe(true);
    expect(byId[UUID_B]).toBe(false);
    expect(result.current.unreadCount).toBe(1);
  });

  it('does not post derived alerts', async () => {
    mockListAlertsFeed.mockResolvedValue([feedItem(UUID_A, false)]);
    mockListItems.mockResolvedValue([DERIVED_ITEM]);
    const { result } = await renderFeed();

    await act(async () => { await result.current.markAllAsRead(); });

    expect(mockMarkTriggerRead).toHaveBeenCalledTimes(1);
    expect(mockMarkTriggerRead).toHaveBeenCalledWith(UUID_A);
  });
});
