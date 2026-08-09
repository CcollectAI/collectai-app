/**
 * Pins the client-wide PostgREST timeout.
 *
 * Regression guard for the bug class that shipped three times: supabase-js has
 * no per-request timeout, so a query stalled behind the auth lock pins a
 * skeleton or a "Saving…" button forever with no error and nothing logged.
 *
 * The properties that actually matter:
 *   1. a hanging query SETTLES (does not hang)
 *   2. it settles as { data: null, error } — the shape callers already handle —
 *      and does NOT throw, or we would trade silent hangs for red screens
 *   3. chained builders stay bounded (.select().eq().single())
 *   4. auth.* is NOT wrapped — racing it can revoke the session
 */
import type { SupabaseClient } from '@supabase/supabase-js';
import { installRequestTimeouts } from '@/lib/supabase';

// `@/utils/logger` is now a re-export of this module, so the mock must keep
// createLogger present or every downstream importer breaks at require time.
jest.mock('@/lib/logger', () => {
  const noop = () => ({ debug: jest.fn(), info: jest.fn(), warn: jest.fn(), error: jest.fn() });
  return {
    logger: { error: jest.fn(), warn: jest.fn(), info: jest.fn(), debug: jest.fn() },
    createLogger: jest.fn(noop),
    getRecentLogs: jest.fn(() => []),
    clearRecentLogs: jest.fn(),
  };
});

/** Builder whose `then` never settles, mimicking a stall behind the auth lock. */
function hangingBuilder() {
  const builder: Record<string, unknown> = {};
  for (const m of ['select', 'eq', 'order', 'limit', 'single', 'insert', 'update']) {
    builder[m] = () => builder;
  }
  builder.then = () => {}; // never resolves, never rejects
  return builder;
}

function settlingBuilder(value: unknown) {
  const builder: Record<string, unknown> = {};
  for (const m of ['select', 'eq', 'order', 'limit', 'single', 'insert', 'update']) {
    builder[m] = () => builder;
  }
  builder.then = (res: (v: unknown) => void) => { res(value); };
  return builder;
}

/**
 * Awaits a bounded builder under fake timers. `.then` must be invoked
 * SYNCHRONOUSLY so the timeout timer exists before we advance the clock —
 * `await` defers it to a microtask and the advance would be a no-op.
 */
function settleWithTimers(thenable: unknown): Promise<unknown> {
  const p = new Promise((resolve) => {
    (thenable as { then: (r: (v: unknown) => void) => void }).then(resolve);
  });
  jest.advanceTimersByTime(15_000);
  return p;
}

function fakeClient(builderFactory: () => unknown) {
  const authGetSession = jest.fn();
  return {
    from: () => builderFactory(),
    rpc: () => builderFactory(),
    auth: { getSession: authGetSession },
  } as unknown as SupabaseClient;
}

describe('supabase client-wide request timeout', () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  it('settles a hanging query instead of hanging forever', async () => {
    const client = installRequestTimeouts(fakeClient(hangingBuilder));
    await expect(settleWithTimers(client.from('items').select('*'))).resolves.toBeDefined();
  });

  it('returns { data: null, error } rather than throwing', async () => {
    const client = installRequestTimeouts(fakeClient(hangingBuilder));
    const res = (await settleWithTimers(client.from('items').select('*'))) as { data: unknown; error: { code: string } };
    expect(res.data).toBeNull();
    expect(res.error.code).toBe('TIMEOUT');
  });

  it('keeps the bound across a chained builder', async () => {
    const client = installRequestTimeouts(fakeClient(hangingBuilder));
    const res = (await settleWithTimers(
      client.from('items').select('id').eq('id', 'x').single(),
    )) as { error: { code: string } };
    expect(res.error.code).toBe('TIMEOUT');
  });

  it('bounds rpc() too', async () => {
    const client = installRequestTimeouts(fakeClient(hangingBuilder));
    const res = (await settleWithTimers(client.rpc('some_fn', {}))) as { error: { code: string } };
    expect(res.error.code).toBe('TIMEOUT');
  });

  it('passes a normal result straight through, untouched', async () => {
    const payload = { data: [{ id: 'a' }], error: null };
    const client = installRequestTimeouts(fakeClient(() => settlingBuilder(payload)));
    await expect(client.from('items').select('*')).resolves.toEqual(payload);
  });

  it('does NOT wrap auth (racing it can revoke the session)', () => {
    const client = fakeClient(hangingBuilder);
    const before = client.auth.getSession;
    installRequestTimeouts(client);
    expect(client.auth.getSession).toBe(before);
  });
});
