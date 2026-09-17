/**
 * What a mutation makes wrong, it must forget.
 *
 * 2026-09-17 (class F): the five item mutations each cleared items + portfolio
 * and nothing else, so adding or deleting an item left `categories:summaries`
 * (TTL 15 min) with the old per-category counts and `analytics:metrics` with the
 * old totals — while creating a build-paint project DID clear analytics. Five
 * copies of one list is how one of them stays wrong, so the keys now live in a
 * single method.
 *
 * And a profile lives in TWO caches: userProvider's in-process Map and the
 * SQLite `profile:<id>` entry. Privacy settings cleared only the first, Edit
 * profile neither.
 */
const cleared: string[] = [];
jest.mock('../../src/data/offlineCache', () => ({
  cacheGet: jest.fn().mockResolvedValue(null),
  cacheSet: jest.fn().mockResolvedValue(undefined),
  cacheClear: jest.fn((prefix?: string) => { cleared.push(prefix ?? '<ALL>'); return Promise.resolve(); }),
}));
const mockClearProfileCache = jest.fn();
jest.mock('../../src/data/providers/userProvider', () => ({
  clearProfileCache: () => mockClearProfileCache(),
}));
jest.mock('../../src/utils/logger', () => ({
  __esModule: true,
  default: { info: jest.fn(), warn: jest.fn(), error: jest.fn() },
}));

import { CachedDataProvider, clearProfileCaches } from '../../src/data/CachedDataProvider';
import type { DataProvider } from '../../src/data/DataProvider';

const inner = {
  createItem: jest.fn().mockResolvedValue({ id: 'i1' }),
  deleteItem: jest.fn().mockResolvedValue(undefined),
  updateItem: jest.fn().mockResolvedValue({ id: 'i1' }),
  archiveItem: jest.fn().mockResolvedValue(undefined),
  unarchiveItem: jest.fn().mockResolvedValue(undefined),
} as unknown as DataProvider;

const provider = new CachedDataProvider(inner);

// Every cache whose contents an item change invalidates.
const ITEM_KEYS = [
  'items:list',
  'portfolio:summary',
  'categories:summaries',
  'category:missing',
  'analytics:metrics',
];

describe('an item change forgets every cache it makes wrong', () => {
  beforeEach(() => { cleared.length = 0; });

  const mutations: [string, () => Promise<unknown>][] = [
    ['createItem', () => provider.createItem({ name: 'x' } as never)],
    ['deleteItem', () => provider.deleteItem('i1')],
    ['updateItem', () => provider.updateItem('i1', { name: 'y' })],
    ['archiveItem', () => provider.archiveItem('i1')],
    ['unarchiveItem', () => provider.unarchiveItem('i1')],
  ];

  for (const [name, run] of mutations) {
    it(`${name} clears all ${ITEM_KEYS.length} keys`, async () => {
      await run();
      for (const key of ITEM_KEYS) expect(cleared).toContain(key);
    });
  }
});

describe('clearProfileCaches', () => {
  beforeEach(() => { cleared.length = 0; mockClearProfileCache.mockClear(); });

  it('clears BOTH the in-process map and the SQLite profile entries', async () => {
    await clearProfileCaches();
    expect(mockClearProfileCache).toHaveBeenCalled();
    expect(cleared).toContain('profile:');
  });
});
