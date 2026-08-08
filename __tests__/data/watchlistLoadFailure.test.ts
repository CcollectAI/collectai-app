/**
 * A failed watchlist read must THROW, never resolve to [].
 *
 * The bug: listWatchlist caught its errors and returned an empty array, so the
 * screen rendered "No items in your watchlist yet" — telling a user their saved
 * items were gone when the read had simply failed. `logger.warn` on that path is
 * stripped from release builds, so it was also invisible on exactly the builds
 * where it matters.
 *
 * This is worse than the usual silent-empty because the watchlist IS the input
 * to the paid feature (_check_watchlist_snipes reads target_price). A user who
 * believes their watchlist emptied has no reason to keep paying for alerts on it.
 */
import { TimeoutError } from '../../src/lib/withTimeout';

const mockSelect = jest.fn();
jest.mock('../../src/lib/supabase', () => ({
  supabase: { from: () => ({ select: (...a: unknown[]) => mockSelect(...a) }) },
}));
jest.mock('../../src/utils/logger', () => ({
  __esModule: true,
  default: { info: jest.fn(), warn: jest.fn(), error: jest.fn() },
}));

import { listWatchlist } from '../../src/data/providers/watchlistProvider';
import logger from '../../src/utils/logger';

describe('listWatchlist failure handling', () => {
  beforeEach(() => jest.clearAllMocks());

  it('THROWS when supabase returns an error — never a silent empty list', async () => {
    mockSelect.mockResolvedValue({ data: null, error: { message: 'JWT expired' } });
    await expect(listWatchlist('u1')).rejects.toThrow('JWT expired');
  });

  it('logs that failure at ERROR, not warn (warn is stripped in release)', async () => {
    mockSelect.mockResolvedValue({ data: null, error: { message: 'JWT expired' } });
    await expect(listWatchlist('u1')).rejects.toThrow();
    expect(logger.error).toHaveBeenCalled();
    expect(logger.warn).not.toHaveBeenCalled();
  });

  it('THROWS on timeout rather than returning []', async () => {
    mockSelect.mockImplementation(() => new Promise(() => {}));  // never settles
    await expect(listWatchlist('u1')).rejects.toBeInstanceOf(TimeoutError);
  }, 20000);

  it('still returns rows normally when the read succeeds', async () => {
    mockSelect.mockResolvedValue({
      data: [{ id: 'w1', title: 'Bayou', priority: 'high', owned: false,
               target_price: 300, currency: 'EUR', category: 'mtg' }],
      error: null,
    });
    const rows = await listWatchlist('u1');
    expect(rows).toHaveLength(1);
    expect(rows[0].targetPrice).toBe(300);
  });

  it('an EMPTY result is still an empty array — the two must stay distinguishable', async () => {
    // The whole point: genuinely-empty resolves, failure rejects. If this ever
    // starts rejecting, the empty state becomes unreachable.
    mockSelect.mockResolvedValue({ data: [], error: null });
    await expect(listWatchlist('u1')).resolves.toEqual([]);
  });
});
