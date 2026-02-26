/**
 * offlineCache tests.
 *
 * Verifies the SQLite-backed key/value cache operations:
 * - cacheSet stores a value that cacheGet retrieves
 * - Expired entries return null
 * - cacheClear removes entries (all or by prefix)
 *
 * Uses __setDbForTesting to inject a mock db directly, avoiding
 * issues with jest.mock and dynamic import().
 */
import { cacheGet, cacheSet, cacheClear, cacheEvictExpired, __setDbForTesting } from '../../src/data/offlineCache';

// ---------------------------------------------------------------------------
// In-memory mock for the SQLite db object
// ---------------------------------------------------------------------------

type Row = { key: string; data: string; expires_at: number };

let store: Map<string, Row>;

const mockExecAsync = jest.fn();
const mockGetFirstAsync = jest.fn();
const mockRunAsync = jest.fn();

jest.mock('../../src/utils/logger', () => ({
  __esModule: true,
  default: {
    info: jest.fn(),
    warn: jest.fn(),
    error: jest.fn(),
  },
}));

// ---------------------------------------------------------------------------
// Wire the mocks to an in-memory store
// ---------------------------------------------------------------------------

beforeEach(() => {
  store = new Map();

  mockExecAsync.mockResolvedValue(undefined);

  // SELECT — look up a row by key
  mockGetFirstAsync.mockImplementation((_sql: string, params: any[]) => {
    const key = params[0] as string;
    const row = store.get(key);
    if (!row) return Promise.resolve(null);
    return Promise.resolve({ data: row.data, expires_at: row.expires_at });
  });

  // INSERT OR REPLACE / DELETE
  mockRunAsync.mockImplementation((sql: string, params: any[]) => {
    if (sql.includes('INSERT OR REPLACE')) {
      const [key, data, expiresAt] = params as [string, string, number];
      store.set(key, { key, data, expires_at: expiresAt });
      return Promise.resolve({ changes: 1 });
    }
    if (sql.includes('DELETE') && sql.includes('LIKE')) {
      const prefix = (params[0] as string).replace('%', '');
      let deleted = 0;
      for (const k of [...store.keys()]) {
        if (k.startsWith(prefix)) {
          store.delete(k);
          deleted++;
        }
      }
      return Promise.resolve({ changes: deleted });
    }
    if (sql.includes('DELETE') && sql.includes('expires_at')) {
      const now = params[0] as number;
      let deleted = 0;
      for (const [k, v] of [...store.entries()]) {
        if (v.expires_at <= now) {
          store.delete(k);
          deleted++;
        }
      }
      return Promise.resolve({ changes: deleted });
    }
    if (sql.includes('DELETE') && sql.includes('key = ?')) {
      const key = params[0] as string;
      const had = store.has(key);
      store.delete(key);
      return Promise.resolve({ changes: had ? 1 : 0 });
    }
    if (sql === 'DELETE FROM cache') {
      const size = store.size;
      store.clear();
      return Promise.resolve({ changes: size });
    }
    return Promise.resolve({ changes: 0 });
  });

  // Inject mock db directly — bypasses dynamic import('expo-sqlite')
  __setDbForTesting({
    execAsync: (...args: any[]) => mockExecAsync(...args),
    getFirstAsync: (...args: any[]) => mockGetFirstAsync(...args),
    runAsync: (...args: any[]) => mockRunAsync(...args),
  });
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('offlineCache', () => {
  it('cacheSet + cacheGet round-trips a value', async () => {
    await cacheSet('items:list', { ids: [1, 2, 3] });
    const result = await cacheGet<{ ids: number[] }>('items:list');
    expect(result).toEqual({ ids: [1, 2, 3] });
  });

  it('cacheGet returns null for a missing key', async () => {
    const result = await cacheGet('nonexistent');
    expect(result).toBeNull();
  });

  it('cacheGet returns null for an expired entry', async () => {
    // Store with a TTL of 0ms (already expired)
    await cacheSet('expired-key', 'old-data', 0);

    // Manually patch the expires_at to be in the past
    const row = store.get('expired-key');
    if (row) {
      row.expires_at = Date.now() - 1;
    }

    const result = await cacheGet('expired-key');
    expect(result).toBeNull();
  });

  it('cacheClear without prefix clears all entries', async () => {
    await cacheSet('a', 1);
    await cacheSet('b', 2);
    expect(store.size).toBe(2);

    await cacheClear();
    expect(store.size).toBe(0);
  });

  it('cacheClear with prefix only removes matching keys', async () => {
    await cacheSet('items:list', [1]);
    await cacheSet('items:detail:42', { id: 42 });
    await cacheSet('portfolio:summary', { total: 100 });
    expect(store.size).toBe(3);

    await cacheClear('items:');
    expect(store.size).toBe(1);
    expect(store.has('portfolio:summary')).toBe(true);
  });

  it('cacheEvictExpired removes only expired rows', async () => {
    await cacheSet('fresh', 'ok', 60_000);
    await cacheSet('stale', 'expired', 0);

    // Force the stale entry into the past
    const row = store.get('stale');
    if (row) {
      row.expires_at = Date.now() - 1;
    }

    const deleted = await cacheEvictExpired();
    expect(deleted).toBe(1);
    expect(store.has('fresh')).toBe(true);
    expect(store.has('stale')).toBe(false);
  });
});
