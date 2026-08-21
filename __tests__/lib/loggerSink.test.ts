/**
 * Pins the log sink that carries retained logs to Sentry.
 *
 * WHY THIS EXISTS
 *
 * `logger.error` wrote to the console and nowhere else. Sentry was initialised
 * the whole time and never received a line of it, so the one diagnostic built
 * to triage the paywall — "[subscription] iapUnavailable reason=no-offering" —
 * could not be read off a TestFlight device without a cable and Console.app.
 *
 * THE HAZARD THIS FILE REALLY GUARDS
 *
 * Sentry's `beforeSend` AND `beforeBreadcrumb` hooks in app/_layout.tsx both
 * call `logger.error(...)` from their own catch blocks. A sink that forwards
 * to Sentry is therefore re-entrant by construction: log -> sink -> Sentry ->
 * hook throws -> logger.error -> sink -> ... until the stack blows. The
 * diagnostic channel would become the crash it was added to report, and it
 * would only do so on the builds where something was already going wrong.
 *
 * `notifySink`'s `inSink` latch is the guard. The recursion test below fails
 * without it (verified by removing the latch: RangeError, maximum call stack).
 */
import {
  createLogger,
  getRecentLogs,
  clearRecentLogs,
  setLogSink,
  type RetainedLog,
} from '@/lib/logger';

describe('logger sink', () => {
  beforeEach(() => {
    clearRecentLogs();
    setLogSink(null);
  });
  afterAll(() => setLogSink(null));

  it('forwards every retained entry to a registered sink', () => {
    const seen: RetainedLog[] = [];
    setLogSink((e) => seen.push(e));
    const log = createLogger();
    log.error('boom');
    expect(seen).toHaveLength(1);
    expect(seen[0].level).toBe('error');
    expect(seen[0].message).toContain('boom');
  });

  it('carries the level so the sink can pick events vs breadcrumbs', () => {
    const levels: string[] = [];
    setLogSink((e) => levels.push(e.level));
    const log = createLogger();
    log.warn('w');
    log.error('e');
    // _layout.tsx sends error -> captureMessage and warn -> addBreadcrumb, so
    // the level has to survive the hop or both collapse into one channel.
    expect(levels).toEqual(['warn', 'error']);
  });

  it('does NOT recurse when the sink itself logs (the Sentry beforeSend shape)', () => {
    const log = createLogger();
    let calls = 0;
    setLogSink(() => {
      calls += 1;
      // Exactly what Sentry's beforeSend/beforeBreadcrumb catch blocks do.
      log.error('[silent-catch] sink failed');
    });
    expect(() => log.error('original failure')).not.toThrow();
    // One entry in, one sink call out. Re-entrant calls are dropped, not queued.
    expect(calls).toBe(1);
  });

  it('keeps logging when the sink throws', () => {
    setLogSink(() => {
      throw new Error('sentry exploded');
    });
    const log = createLogger();
    expect(() => log.error('still recorded')).not.toThrow();
    // The ring buffer is the durable copy; a broken sink must not cost the entry.
    expect(getRecentLogs('error').some((l) => l.message.includes('still recorded'))).toBe(true);
  });

  it('detaches on setLogSink(null)', () => {
    let calls = 0;
    setLogSink(() => {
      calls += 1;
    });
    const log = createLogger();
    log.error('one');
    setLogSink(null);
    log.error('two');
    expect(calls).toBe(1);
  });

  it('retains entries when no sink is registered at all', () => {
    const log = createLogger();
    log.error('no sink here');
    expect(getRecentLogs('error').some((l) => l.message.includes('no sink here'))).toBe(true);
  });
});
