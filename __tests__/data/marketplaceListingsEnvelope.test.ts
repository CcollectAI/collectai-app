/**
 * Seller Dashboard envelope contract.
 *
 * `GET /marketplace/listings` and `/marketplace/listings/sales` return an
 * ENVELOPE — `{ listings: [...], total_count }` and `{ sales: [...],
 * total_count }` — while `/accounts` and `/fees` return bare arrays. The
 * provider signatures promised `Promise<T[]>` for all four, so the dashboard
 * received an object where it expected an array and
 * `for (const s of sales)` threw:
 *
 *     TypeError: iterator method is not callable
 *
 * The whole screen fell into its ScreenErrorBoundary and rendered
 * "Seller Dashboard failed to load" — on BOTH platforms, since nothing here is
 * Android-specific. `dashboardData?.sales ?? []` did not save it, because an
 * object is truthy; only comparing the VALUE's shape finds this.
 *
 * Shapes verified against production 2026-08-01 with a real user token.
 *
 * These tests fail against the pre-fix provider (which returned the raw
 * response) and pass after it unwraps.
 */

const mockGet = jest.fn();

jest.mock('@/api/collectorsApi', () => ({
  collectorsApi: {
    get: (...args: unknown[]) => mockGet(...args),
    post: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
  },
}));

import {
  listMarketplaceListings,
  listMarketplaceSales,
  listMarketplaceAccounts,
  getMarketplaceFeeSchedules,
} from '@/data/providers/dealsProvider';

beforeEach(() => mockGet.mockReset());

describe('marketplace provider unwraps the API envelope', () => {
  it('listMarketplaceListings returns the inner array, not the envelope', async () => {
    mockGet.mockResolvedValue({ listings: [{ id: 'l1' }, { id: 'l2' }], total_count: 2 });
    const res = await listMarketplaceListings();
    expect(Array.isArray(res)).toBe(true);
    expect(res).toHaveLength(2);
    // The actual crash: iterating the un-unwrapped envelope.
    expect(() => { for (const _ of res) { /* must not throw */ } }).not.toThrow();
  });

  it('listMarketplaceSales returns the inner array', async () => {
    mockGet.mockResolvedValue({ sales: [{ id: 's1' }], total_count: 1 });
    await expect(listMarketplaceSales()).resolves.toEqual([{ id: 's1' }]);
  });

  it('passes bare arrays through untouched (accounts, fees)', async () => {
    mockGet.mockResolvedValue([{ id: 'a1' }]);
    await expect(listMarketplaceAccounts()).resolves.toEqual([{ id: 'a1' }]);
    mockGet.mockResolvedValue([{ marketplace: 'ebay' }]);
    await expect(getMarketplaceFeeSchedules()).resolves.toEqual([{ marketplace: 'ebay' }]);
  });

  it('never yields a non-iterable, whatever the API returns', async () => {
    for (const weird of [null, undefined, {}, { total_count: 0 }, 42, 'nope']) {
      mockGet.mockResolvedValue(weird);
      const res = await listMarketplaceSales();
      expect(Array.isArray(res)).toBe(true);
      expect(() => { for (const _ of res) { /* no throw */ } }).not.toThrow();
    }
  });
});
