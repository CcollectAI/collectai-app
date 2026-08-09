/**
 * Pins the single-logger collapse and the retained buffer.
 *
 * There used to be two logger implementations with different production
 * semantics — `@/utils/logger` stripped `warn` behind __DEV__, `@/lib/logger`
 * always printed it — so whether a failure survived into a release build
 * depended on which import a file happened to have. 139 catch blocks logged
 * only via warn/info from the stripping copy, leaving no trace at all in the
 * build where it mattered.
 *
 * The properties that matter:
 *   1. both import paths resolve to ONE implementation
 *   2. every level is retained even when it is not printed
 *   3. the buffer is bounded, so it cannot grow without limit
 *   4. getRecentLogs can filter to the levels that indicate a failure
 */
import { createLogger, getRecentLogs, clearRecentLogs } from '@/lib/logger';
import defaultLogger from '@/utils/logger';

describe('logger retention', () => {
  beforeEach(() => clearRecentLogs());

  it('retains debug/info even though release builds do not print them', () => {
    const log = createLogger({ prefix: 'T' });
    log.debug('a debug line');
    log.info('an info line');
    const levels = getRecentLogs().map((l) => l.level);
    expect(levels).toEqual(expect.arrayContaining(['debug', 'info']));
  });

  it('retains warn and error', () => {
    const log = createLogger();
    log.warn('a warning');
    log.error('an error');
    const levels = getRecentLogs().map((l) => l.level);
    expect(levels).toEqual(expect.arrayContaining(['warn', 'error']));
  });

  it('filters by minimum level so failures can be isolated', () => {
    const log = createLogger();
    log.debug('noise');
    log.info('noise');
    log.warn('a real problem');
    log.error('a worse problem');
    const serious = getRecentLogs('warn');
    expect(serious).toHaveLength(2);
    expect(serious.every((l) => l.level === 'warn' || l.level === 'error')).toBe(true);
  });

  it('bounds the buffer rather than growing forever', () => {
    const log = createLogger();
    for (let i = 0; i < 500; i++) log.info(`line ${i}`);
    const all = getRecentLogs();
    expect(all.length).toBeLessThanOrEqual(300);
    // Oldest entries are evicted, newest kept.
    expect(all[all.length - 1].message).toContain('line 499');
  });

  it('survives an unserialisable payload instead of throwing', () => {
    const circular: Record<string, unknown> = {};
    circular.self = circular;
    const log = createLogger();
    expect(() => log.error('circular:', circular)).not.toThrow();
    expect(getRecentLogs('error')).toHaveLength(1);
  });

  it('the @/utils/logger default export is the same implementation', () => {
    defaultLogger.warn('via the utils path');
    const found = getRecentLogs('warn');
    expect(found).toHaveLength(1);
    expect(found[0].message).toContain('via the utils path');
  });
});
