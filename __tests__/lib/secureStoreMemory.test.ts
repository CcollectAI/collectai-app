/**
 * The secure-store adapter keeps a write-through memory copy (2026-09-26).
 * supabase-js reads storage on every getSession() — every authed request — and
 * each read was a head + N chunk keystore decrypts in series.
 *
 * The copy must never report something the store does not hold, and a slow
 * read of the OLD session must never overwrite a newer write: a rotated
 * refresh token handed back to GoTrue gets the session revoked.
 */
const mockStore = new Map<string, string>();
const mockReads = { n: 0 };
let mockFailWrites = false;
let mockReadGate: Promise<void> | null = null;

jest.mock('expo-secure-store', () => ({
  getItemAsync: async (k: string) => {
    mockReads.n++;
    // Read FIRST, then wait: a slow keystore read returns what was stored when
    // it started. (The first version waited first, read the NEW value, and the
    // race test passed with the generation guard deleted.)
    const v = mockStore.has(k) ? mockStore.get(k)! : null;
    if (mockReadGate) await mockReadGate;
    return v;
  },
  setItemAsync: async (k: string, v: string) => {
    if (mockFailWrites) throw new Error('keystore unavailable');
    mockStore.set(k, v);
  },
  deleteItemAsync: async (k: string) => { mockStore.delete(k); },
}));
jest.mock('../../src/utils/logger', () => ({
  __esModule: true,
  default: { error: jest.fn(), warn: jest.fn(), info: jest.fn() },
}));

import { secureStoreAdapter as s, __resetSecureStoreMemory } from '../../src/lib/secureStoreAdapter';

const BIG = 'x'.repeat(4000); // chunked: > CHUNK_LIMIT

beforeEach(() => {
  mockStore.clear();
  mockReads.n = 0;
  mockFailWrites = false;
  mockReadGate = null;
  __resetSecureStoreMemory();
});

it('reads the keystore once, then serves the same bytes from memory', async () => {
  await s.setItem('k', BIG);
  __resetSecureStoreMemory(); // as on a cold start
  mockReads.n = 0;
  expect(await s.getItem('k')).toBe(BIG);
  const first = mockReads.n;
  expect(await s.getItem('k')).toBe(BIG);
  expect(mockReads.n).toBe(first);
});

it('a successful write is readable without a keystore read', async () => {
  await s.setItem('k', BIG);
  mockReads.n = 0;
  expect(await s.getItem('k')).toBe(BIG);
  expect(mockReads.n).toBe(0);
});

it('a FAILED write is not reported as persisted', async () => {
  await s.setItem('k', 'old');
  mockFailWrites = true;
  await s.setItem('k', 'new');
  mockFailWrites = false;
  expect(await s.getItem('k')).not.toBe('new');
});

it('a slow read of the old value cannot overwrite a newer write', async () => {
  await s.setItem('k', 'old');
  __resetSecureStoreMemory();
  let release!: () => void;
  mockReadGate = new Promise<void>((r) => { release = r; });
  const slowRead = s.getItem('k');            // starts reading 'old'
  mockReadGate = null;
  await s.setItem('k', 'new');                 // lands first
  release();
  await slowRead;                              // finishes last
  expect(await s.getItem('k')).toBe('new');
});
