/**
 * A timed-out collection read must FAIL, not return an empty collection.
 *
 * WHY (2026-09-12, found walking the app on Android): the Items tab opened on
 *
 *     Portfolio total: €0
 *     Start your collection — Add Your First Item
 *
 * for an account holding **€1.348 across 8 items**, and stayed there for 45s+.
 * PostgREST returned those 8 rows to the same JWT throughout — the read had
 * merely timed out, and `listItems` answered `[]`. A pull-to-refresh brought
 * all 8 back.
 *
 * The file already knew better. Its `if (error)` branch throws, with the
 * comment *"THROW, not `return []`. An empty array is indistinguishable from
 * 'you have none'"* — and the timeout branch six lines above it did exactly
 * that. One failure mode reasoned about correctly, its twin not.
 *
 * The empty state is worse than a blank screen here: it does not merely fail
 * to show a collection, it tells a collector they have none and offers to help
 * them start one.
 *
 * `usePaginatedList` maps a TimeoutError to "Timed out loading. Pull to
 * refresh." — an honest sentence it could never reach while this resolved
 * successfully with nothing.
 */
import { jest } from '@jest/globals';

// `withTimeout` is the seam: make it behave exactly as it does when the read
// exceeds ITEMS_READ_TIMEOUT_MS. `requireActual` keeps the REAL TimeoutError
// class, so the provider's `e instanceof TimeoutError` is genuinely exercised
// rather than against a stand-in that would pass either way.
let mockShouldTimeout = true;
jest.mock('../../src/lib/withTimeout', () => {
  const actual = jest.requireActual('../../src/lib/withTimeout') as {
    TimeoutError: new (ms: number, label?: string) => Error;
  };
  return {
    ...actual,
    withTimeout: jest.fn((promise: Promise<unknown>, ms: number, label?: string) =>
      mockShouldTimeout
        ? Promise.reject(new actual.TimeoutError(ms, label))
        : promise,
    ),
  };
});

jest.mock('../../src/lib/supabase', () => {
  const chain: Record<string, unknown> = {};
  const self = () => chain;
  Object.assign(chain, {
    from: jest.fn(self),
    select: jest.fn(self),
    eq: jest.fn(self),
    order: jest.fn(self),
    range: jest.fn(() => Promise.resolve({ data: [], error: null })),
  });
  return { supabase: chain };
});

import { listItems } from '../../src/data/providers/itemsProvider';

describe('listItems when the read times out', () => {
  beforeEach(() => {
    mockShouldTimeout = true;
  });

  it('rejects rather than resolving with an empty collection', async () => {
    await expect(listItems()).rejects.toThrow(/Timed out/i);
  });

  it('rejects with a TimeoutError, which is what maps to "Pull to refresh"', async () => {
    // usePaginatedList branches on `e instanceof TimeoutError` to choose the
    // message, so the TYPE has to survive — a generic Error would silently
    // degrade the copy to "Failed to load items".
    await expect(listItems()).rejects.toMatchObject({ name: 'TimeoutError' });
  });

  it('still returns rows normally when the read does not time out', async () => {
    mockShouldTimeout = false;
    await expect(listItems()).resolves.toEqual([]);
  });
});
