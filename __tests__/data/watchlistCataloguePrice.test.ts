/**
 * Card-linked watches show the catalogue price (2026-10-15).
 *
 * last_market_price's only writer has been off since 2026-05-04, so every watch
 * read "No market price yet". GET /watchlist/mine now carries the catalogue
 * price (same rule as item_value_v1); the list merges it by id, and a failure
 * of that call leaves the list itself intact.
 */
const mockSelect = jest.fn();
const mockGet = jest.fn();
jest.mock('../../src/lib/supabase', () => ({
  supabase: { from: () => ({ select: (...a: unknown[]) => mockSelect(...a) }) },
}));
jest.mock('../../src/api/collectorsApi', () => ({ collectorsApi: { get: (...a: unknown[]) => mockGet(...a) } }));
jest.mock('../../src/utils/logger', () => ({
  __esModule: true,
  default: { info: jest.fn(), warn: jest.fn(), error: jest.fn() },
}));

import { listWatchlist } from '../../src/data/providers/watchlistProvider';

const rows = [
  { id: 'w1', title: 'Charizard ex', priority: 'medium', owned: false, target_price: 30, currency: 'EUR', category: 'pokemon' },
  { id: 'w2', title: 'Black Lotus', priority: 'medium', owned: false, target_price: 12000, currency: 'EUR', category: 'mtg' },
];

describe('listWatchlist — catalogue price', () => {
  beforeEach(() => { jest.clearAllMocks(); mockSelect.mockResolvedValue({ data: rows, error: null }); });

  it('merges the catalogue price and its date by id', async () => {
    mockGet.mockResolvedValue({ items: [
      { id: 'w1', catalog_price_eur: 5.53, catalog_price_as_of: '2026-10-12' },
      { id: 'w2', catalog_price_eur: null, catalog_price_as_of: null },
    ] });
    const out = await listWatchlist('u1');
    expect(mockGet).toHaveBeenCalledWith('/watchlist/mine?limit=200');
    expect(out.find((w) => w.id === 'w1')).toMatchObject({ catalogPriceEur: 5.53, catalogPriceAsOf: '2026-10-12' });
    expect(out.find((w) => w.id === 'w2')?.catalogPriceEur).toBeNull();
  });

  it('keeps the list when the catalogue call fails', async () => {
    mockGet.mockRejectedValue(new Error('429'));
    const out = await listWatchlist('u1');
    expect(out).toHaveLength(2);
    expect(out[0].catalogPriceEur).toBeUndefined();
  });
});
